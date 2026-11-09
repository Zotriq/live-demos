"""Extract: read raw records from each source without changing their meaning.

Each source has its own column names and formats. The extractors only map
columns onto a common set of *raw* fields; all cleaning happens in transform.py
so every rule lives in one place and is unit-tested.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass(frozen=True)
class RawOrder:
    source: str
    source_row: int
    order_ref: str
    email: str
    customer_name: str
    order_date: str
    amount: str
    currency: str
    status: str
    country: str


def read_webstore_csv(path: Path) -> list[RawOrder]:
    """Online store export: comma-separated, US-style amounts like "$1,249.50"."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [
            RawOrder(
                source="webstore",
                source_row=i,
                order_ref=row["order_id"],
                email=row["customer_email"],
                customer_name=row["customer_name"],
                order_date=row["order_date"],
                amount=row["total"],
                currency=row["currency"],
                status=row["status"],
                country=row["country"],
            )
            for i, row in enumerate(csv.DictReader(fh), start=2)
        ]


def read_pos_csv(path: Path) -> list[RawOrder]:
    """In-store POS export: semicolon-separated, European numbers like "18.990,00", dates as DD.MM.YYYY."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [
            RawOrder(
                source="pos",
                source_row=i,
                order_ref=row["Receipt No"],
                email=row["Email"],
                customer_name=row["Customer"],
                order_date=row["Sale Date"],
                amount=row["Amount"],
                currency=row["Cur"],
                status="paid",  # the POS only exports completed sales
                country="Pakistan",  # all outlets are in Pakistan
            )
            for i, row in enumerate(csv.DictReader(fh, delimiter=";"), start=2)
        ]


class FxRatesError(RuntimeError):
    pass


def fetch_fx_rates(
    url: str,
    *,
    fallback_file: Path | None = None,
    client: httpx.Client | None = None,
    retries: int = 3,
    backoff_seconds: float = 0.5,
) -> tuple[dict[str, float], str]:
    """Return (rates per 1 USD, source label). Retries with backoff, then falls back to a file."""
    own_client = client is None
    client = client or httpx.Client(timeout=10)
    last_error: Exception | None = None
    try:
        for attempt in range(1, retries + 1):
            try:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
                rates = payload.get("rates") or payload.get("conversion_rates")
                if not rates or "USD" not in rates:
                    raise FxRatesError("Response has no USD-based rates")
                return {k.upper(): float(v) for k, v in rates.items()}, "api"
            except (httpx.HTTPError, ValueError, FxRatesError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(backoff_seconds * 2 ** (attempt - 1))
    finally:
        if own_client:
            client.close()

    if fallback_file and fallback_file.exists():
        data = json.loads(fallback_file.read_text())
        return {k.upper(): float(v) for k, v in data["rates"].items()}, "fallback"
    raise FxRatesError(f"Could not load exchange rates: {last_error}")
