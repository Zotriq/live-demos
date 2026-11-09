"""Transform: clean, validate, convert currency and de-duplicate raw orders.

Bad rows are never silently dropped: each one comes back as a Rejection with
the reason, and the pipeline stores them so someone can fix the source data.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator

from .extract import RawOrder

VALID_STATUSES = {"pending", "paid", "shipped", "refunded"}

COUNTRY_ALIASES = {
    "pk": "Pakistan",
    "pakistan": "Pakistan",
    "us": "United States",
    "usa": "United States",
    "united states": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "united kingdom": "United Kingdom",
    "it": "Italy",
    "italy": "Italy",
}

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d.%m.%Y", "%d/%m/%Y")


class CleanOrder(BaseModel):
    order_id: str = Field(min_length=1)
    source: str
    email: EmailStr
    customer_name: str = Field(min_length=1)
    country: str
    order_date: dt.date
    status: str
    amount: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    amount_usd: Decimal = Field(ge=0)

    @field_validator("status")
    @classmethod
    def known_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"unknown status '{v}'")
        return v


@dataclass(frozen=True)
class Rejection:
    source: str
    source_row: int
    order_ref: str
    reason: str


def parse_amount(text: str) -> Decimal:
    """Handle "$1,249.50", "1249.5", "18.990,00" (European) and "999,00"."""
    s = re.sub(r"[^\d,.\-]", "", text.strip())
    if not s:
        raise ValueError("amount is empty")
    if "," in s and "." in s:
        # Whichever separator comes last is the decimal point.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head.replace(',', '')}.{tail}" if len(tail) == 2 else s.replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"cannot parse amount '{text}'") from exc


def parse_date(text: str) -> dt.date:
    text = text.strip()
    if not text:
        raise ValueError("order date is missing")
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid date '{text}'")


def normalize_country(text: str) -> str:
    key = text.strip().lower()
    return COUNTRY_ALIASES.get(key, text.strip().title())


def to_usd(amount: Decimal, currency: str, rates: dict[str, float]) -> Decimal:
    if currency not in rates:
        raise ValueError(f"no exchange rate for {currency}")
    usd = amount / Decimal(str(rates[currency]))
    return usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def clean_order(raw: RawOrder, rates: dict[str, float]) -> CleanOrder:
    amount = parse_amount(raw.amount)
    currency = raw.currency.strip().upper()
    return CleanOrder(
        order_id=f"{raw.source}:{raw.order_ref.strip()}",
        source=raw.source,
        email=raw.email.strip().lower(),
        customer_name=" ".join(raw.customer_name.split()),
        country=normalize_country(raw.country),
        order_date=parse_date(raw.order_date),
        status=raw.status.strip().lower(),
        amount=amount,
        currency=currency,
        amount_usd=to_usd(amount, currency, rates),
    )


def _reason(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        err = exc.errors()[0]
        field = ".".join(str(p) for p in err["loc"]) or "record"
        msg = err["msg"].removeprefix("Value error, ")
        return f"{field}: {msg}"
    return str(exc)


def transform(raw_orders: list[RawOrder], rates: dict[str, float]) -> tuple[list[CleanOrder], list[Rejection]]:
    clean: dict[str, CleanOrder] = {}
    rejected: list[Rejection] = []
    for raw in raw_orders:
        try:
            order = clean_order(raw, rates)
        except (ValueError, ValidationError) as exc:
            rejected.append(Rejection(raw.source, raw.source_row, raw.order_ref, _reason(exc)))
            continue
        if order.order_id in clean:
            if clean[order.order_id] != order:
                rejected.append(
                    Rejection(raw.source, raw.source_row, raw.order_ref, "conflicting duplicate of an earlier row")
                )
            continue  # exact duplicates are dropped quietly
        clean[order.order_id] = order
    return list(clean.values()), rejected
