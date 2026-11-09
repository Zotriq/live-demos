"""Generate the sample invoices in examples/sample_invoices/.

- northwind_INV-2041.pdf   clean invoice with a real text layer
- bluepeak_BP-778.pdf      text PDF whose total is wrong (should be flagged)
- scanned_ACME-5512.pdf    image-only "scan" with no text layer (needs OCR)

    python examples/make_sample_invoices.py
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent / "sample_invoices"

INVOICES = [
    {
        "file": "northwind_INV-2041.pdf",
        "vendor": "Northwind Cloud Services LLC", "tax_id": "EIN 84-2219034",
        "number": "INV-2041", "date": "2026-10-01", "due": "2026-10-31",
        "bill_to": "Kelvin Retail Ltd", "symbol": "$",
        "lines": [("Managed hosting - October", 1, 450.00), ("Extra storage (100 GB)", 3, 12.50), ("Support hours", 4, 65.00)],
        "tax_rate": 0.08, "total_override": None,
    },
    {
        "file": "bluepeak_BP-778.pdf",
        "vendor": "BluePeak Design Studio", "tax_id": None,
        "number": "BP-778", "date": "2026-09-14", "due": "2026-09-28",
        "bill_to": "Kelvin Retail Ltd", "symbol": "€",
        "lines": [("Logo redesign", 1, 900.00), ("Social media templates", 10, 35.00)],
        "tax_rate": 0.0, "total_override": 1350.00,  # real sum is 1250.00
    },
    {
        "file": "scanned_ACME-5512.pdf",
        "vendor": "ACME Office Supplies", "tax_id": "NTN 4417782-3",
        "number": "ACME-5512", "date": "2026-10-20", "due": "2026-11-19",
        "bill_to": "Kelvin Retail Ltd", "symbol": "Rs",
        "lines": [("A4 paper (box)", 6, 2400.00), ("Printer toner", 2, 8750.00)],
        "tax_rate": 0.17, "total_override": None, "scanned": True,
    },
]


def money(symbol: str, value: float) -> str:
    return f"{symbol} {value:,.2f}"


def draw(c: canvas.Canvas, inv: dict) -> None:
    w, h = A4
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, h - 60, inv["vendor"])
    c.setFont("Helvetica", 10)
    if inv["tax_id"]:
        c.drawString(50, h - 78, inv["tax_id"])
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(w - 50, h - 60, "INVOICE")
    c.setFont("Helvetica", 11)
    c.drawRightString(w - 50, h - 80, f"Invoice No: {inv['number']}")
    c.drawRightString(w - 50, h - 96, f"Invoice Date: {inv['date']}")
    c.drawRightString(w - 50, h - 112, f"Due Date: {inv['due']}")
    c.drawString(50, h - 130, f"Bill To: {inv['bill_to']}")

    y = h - 180
    c.setFont("Helvetica-Bold", 11)
    for x, label in ((50, "Description"), (330, "Qty"), (390, "Unit Price"), (w - 50, "Amount")):
        (c.drawRightString if label == "Amount" else c.drawString)(x, y, label)
    c.setFont("Helvetica", 11)
    subtotal = 0.0
    for desc, qty, price in inv["lines"]:
        y -= 22
        amount = qty * price
        subtotal += amount
        c.drawString(50, y, desc)
        c.drawString(330, y, str(qty))
        c.drawString(390, y, money(inv["symbol"], price))
        c.drawRightString(w - 50, y, money(inv["symbol"], amount))

    tax = round(subtotal * inv["tax_rate"], 2)
    total = inv["total_override"] if inv["total_override"] is not None else subtotal + tax
    y -= 40
    for label, value in (("Subtotal", subtotal), (f"Tax ({inv['tax_rate']:.0%})", tax), ("Total", total)):
        c.setFont("Helvetica-Bold" if label == "Total" else "Helvetica", 11)
        c.drawString(390, y, label)
        c.drawRightString(w - 50, y, money(inv["symbol"], value))
        y -= 18


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for inv in INVOICES:
        if not inv.get("scanned"):
            c = canvas.Canvas(str(OUT / inv["file"]), pagesize=A4)
            draw(c, inv)
            c.save()
            continue
        # Render to an image, then wrap the image in a PDF with no text layer.
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        draw(c, inv)
        c.save()
        import pdfplumber

        with pdfplumber.open(io.BytesIO(buf.getvalue())) as pdf:
            img = pdf.pages[0].to_image(resolution=200).original.convert("L")
        img = img.rotate(0.6, expand=True, fillcolor=255)  # slightly crooked, like a real scan
        img.save(OUT / inv["file"], "PDF", resolution=200)
    print("Wrote", ", ".join(i["file"] for i in INVOICES))


if __name__ == "__main__":
    main()
