"""Business checks that catch extraction mistakes *and* real invoice errors.

LLMs occasionally misread a digit. Because invoices are self-checking
(quantity x price = amount, lines add up to the subtotal, subtotal + tax = total),
any misread almost always breaks one of these sums and the invoice is flagged
for a human instead of flowing silently into accounting.
"""

from __future__ import annotations

from decimal import Decimal

from .schema import Invoice

TOLERANCE = Decimal("0.02")


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def check_invoice(inv: Invoice) -> list[str]:
    issues: list[str] = []

    if not inv.line_items:
        issues.append("No line items found")

    for i, item in enumerate(inv.line_items, start=1):
        expected = item.quantity * item.unit_price
        if not _close(expected, item.amount):
            issues.append(
                f"Line {i} ({item.description}): {item.quantity} x {item.unit_price} = {expected}, but amount is {item.amount}"
            )

    lines_sum = sum((item.amount for item in inv.line_items), Decimal("0"))
    subtotal = inv.subtotal if inv.subtotal is not None else lines_sum
    if inv.subtotal is not None and not _close(lines_sum, inv.subtotal):
        issues.append(f"Line items add up to {lines_sum}, but subtotal is {inv.subtotal}")

    if not _close(subtotal + inv.tax, inv.total):
        issues.append(f"Subtotal {subtotal} + tax {inv.tax} = {subtotal + inv.tax}, but total is {inv.total}")

    if inv.total <= 0:
        issues.append("Total must be greater than zero")

    if inv.due_date and inv.due_date < inv.invoice_date:
        issues.append(f"Due date {inv.due_date} is before invoice date {inv.invoice_date}")

    if len(inv.currency) != 3 or not inv.currency.isalpha():
        issues.append(f"Currency '{inv.currency}' is not an ISO code")

    return issues
