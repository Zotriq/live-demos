from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: Decimal = Field(description="Number of units; use 1 if not shown")
    unit_price: Decimal = Field(description="Price per unit, without currency symbol")
    amount: Decimal = Field(description="Line total as printed on the invoice")


class Invoice(BaseModel):
    vendor_name: str
    vendor_tax_id: str | None = Field(None, description="VAT / NTN / EIN of the seller if printed")
    invoice_number: str
    invoice_date: dt.date
    due_date: dt.date | None = None
    bill_to: str | None = Field(None, description="Customer company or person the invoice is addressed to")
    currency: str = Field(description="ISO 4217 code, e.g. USD, EUR, PKR")
    line_items: list[LineItem]
    subtotal: Decimal | None = None
    tax: Decimal = Decimal("0")
    total: Decimal


class ExtractionResult(BaseModel):
    file: str
    status: str  # "ok" | "needs_review" | "failed"
    text_source: str | None = None  # "pdf_text" | "ocr"
    invoice: Invoice | None = None
    issues: list[str] = Field(default_factory=list)
