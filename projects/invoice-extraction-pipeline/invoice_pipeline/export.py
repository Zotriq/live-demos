"""Write results to CSV, Excel, JSON or Google Sheets."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .schema import ExtractionResult

INVOICE_COLUMNS = [
    "file", "status", "vendor_name", "vendor_tax_id", "invoice_number", "invoice_date", "due_date",
    "bill_to", "currency", "subtotal", "tax", "total", "issues",
]
LINE_COLUMNS = ["file", "invoice_number", "line", "description", "quantity", "unit_price", "amount"]


def invoice_rows(results: list[ExtractionResult]) -> list[list[str]]:
    rows = []
    for r in results:
        inv = r.invoice
        rows.append([
            r.file,
            r.status,
            inv.vendor_name if inv else "",
            (inv.vendor_tax_id or "") if inv else "",
            inv.invoice_number if inv else "",
            inv.invoice_date.isoformat() if inv else "",
            inv.due_date.isoformat() if inv and inv.due_date else "",
            (inv.bill_to or "") if inv else "",
            inv.currency if inv else "",
            str(inv.subtotal) if inv and inv.subtotal is not None else "",
            str(inv.tax) if inv else "",
            str(inv.total) if inv else "",
            " | ".join(r.issues),
        ])
    return rows


def line_rows(results: list[ExtractionResult]) -> list[list[str]]:
    return [
        [r.file, r.invoice.invoice_number, str(i), item.description, str(item.quantity), str(item.unit_price), str(item.amount)]
        for r in results
        if r.invoice
        for i, item in enumerate(r.invoice.line_items, start=1)
    ]


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def export_csv(results: list[ExtractionResult], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / "invoices.csv", out_dir / "line_items.csv"]
    _write_csv(paths[0], INVOICE_COLUMNS, invoice_rows(results))
    _write_csv(paths[1], LINE_COLUMNS, line_rows(results))
    return paths


def export_json(results: list[ExtractionResult], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "invoices.json"
    path.write_text(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
    return path


def export_excel(results: list[ExtractionResult], out_dir: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    out_dir.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    sheets = [("Invoices", INVOICE_COLUMNS, invoice_rows(results)), ("Line items", LINE_COLUMNS, line_rows(results))]
    review_fill = PatternFill("solid", fgColor="FFF2CC")
    for idx, (title, header, rows) in enumerate(sheets):
        ws = wb.active if idx == 0 else wb.create_sheet()
        ws.title = title
        ws.append(header)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in rows:
            ws.append(row)
            if title == "Invoices" and row[1] != "ok":
                for cell in ws[ws.max_row]:
                    cell.fill = review_fill
        ws.freeze_panes = "A2"
    path = out_dir / "invoices.xlsx"
    wb.save(path)
    return path


def export_google_sheet(results: list[ExtractionResult], spreadsheet_id: str, credentials_file: str) -> None:
    """Append rows to the 'Invoices' and 'Line items' tabs of a Google Sheet (service account)."""
    import gspread

    sheet = gspread.service_account(filename=credentials_file).open_by_key(spreadsheet_id)
    for title, header, rows in (("Invoices", INVOICE_COLUMNS, invoice_rows(results)), ("Line items", LINE_COLUMNS, line_rows(results))):
        try:
            ws = sheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(title, rows=1000, cols=len(header))
            ws.append_row(header)
        if rows:
            ws.append_rows(rows, value_input_option="USER_ENTERED")
