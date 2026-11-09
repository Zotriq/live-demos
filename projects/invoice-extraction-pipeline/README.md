# Invoice Extraction Pipeline

![tests](https://github.com/Zotriq/invoice-extraction-pipeline/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Tesseract](https://img.shields.io/badge/OCR-Tesseract-5A5A5A?style=flat-square)
![OpenAI](https://img.shields.io/badge/OpenAI-structured%20outputs-412991?style=flat-square&logo=openai&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-tool%20use-D97757?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)

Turns a folder of **invoice PDFs and scans** into clean, structured data (vendor, dates, line items,
tax, totals) and **checks the maths** before anything reaches your accounting system.

Use it from the command line, or call the HTTP API from n8n, Make, Zapier or your own app.

## How it works

```
PDF / scan / photo
   │
   ├─ has a text layer? ──► pdfplumber text          (fast, exact)
   └─ scanned image?    ──► Tesseract OCR at 300 dpi
   │
   ▼
LLM extraction into a strict schema
   • OpenAI: structured outputs (json_schema)
   • Claude: forced tool call with the schema as input
   │
   ▼
Validation (Pydantic + accounting checks)
   • qty × unit price = line amount
   • line items add up to the subtotal
   • subtotal + tax = total
   • due date after invoice date, valid currency
   • same vendor + invoice number seen twice → possible duplicate
   │
   ▼
status: ok | needs_review | failed   →   CSV · Excel · JSON · Google Sheets · API response
```

**Why the checks matter:** an LLM or OCR engine that misreads one digit almost always breaks one of these sums.
The pipeline catches it and sends that invoice for human review, instead of letting it flow silently into
QuickBooks or Xero. It also catches genuine billing mistakes from suppliers.

## Example

Three sample invoices are in [`examples/sample_invoices`](examples/sample_invoices): a normal text PDF, a
**scanned image-only PDF** (no text layer), and an invoice whose **total is wrong**.

```text
$ invoice-extract examples/sample_invoices --out output

3 invoices: 2 ok, 1 need review or failed
  - bluepeak_BP-778.pdf [needs_review]: Subtotal 1250.0 + tax 0 = 1250.0, but total is 1350.0
Written: output/invoices.csv, output/line_items.csv, output/invoices.json, output/invoices.xlsx
```

The scanned invoice is read with OCR automatically. In the Excel file, invoices that need review are highlighted.

<details>
<summary>JSON output for one invoice</summary>

```json
{
  "file": "northwind_INV-2041.pdf",
  "status": "ok",
  "text_source": "pdf_text",
  "invoice": {
    "vendor_name": "Northwind Cloud Services LLC",
    "vendor_tax_id": "EIN 84-2219034",
    "invoice_number": "INV-2041",
    "invoice_date": "2026-10-01",
    "due_date": "2026-10-31",
    "bill_to": "Kelvin Retail Ltd",
    "currency": "USD",
    "line_items": [
      { "description": "Managed hosting - October", "quantity": "1", "unit_price": "450.0", "amount": "450.0" },
      { "description": "Extra storage (100 GB)", "quantity": "3", "unit_price": "12.5", "amount": "37.5" },
      { "description": "Support hours", "quantity": "4", "unit_price": "65.0", "amount": "260.0" }
    ],
    "subtotal": "747.5",
    "tax": "59.8",
    "total": "807.3"
  },
  "issues": []
}
```
</details>

## Quick start

Requires Python 3.11+ and [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html)
(`brew install tesseract` / `apt install tesseract-ocr`).

```bash
git clone https://github.com/Zotriq/invoice-extraction-pipeline.git
cd invoice-extraction-pipeline
pip install -e .
cp .env.example .env                 # add your OpenAI or Anthropic key

invoice-extract ./my_invoices --out ./output
invoice-extract ./my_invoices --provider anthropic
```

### Send results to Google Sheets

```bash
pip install -e ".[sheets]"
invoice-extract ./my_invoices --sheet-id <spreadsheet-id> --credentials service_account.json
```

Rows are appended to `Invoices` and `Line items` tabs (created if missing). Share the sheet with the service
account's email first.

### HTTP API (for n8n / Make / Zapier)

```bash
uvicorn invoice_pipeline.api:app --reload
# or: docker build -t invoice-api . && docker run -p 8000:8000 --env-file .env invoice-api

curl -F "file=@examples/sample_invoices/bluepeak_BP-778.pdf" http://localhost:8000/extract
```

In n8n: *Gmail trigger (attachment)* → *HTTP Request* (POST multipart to `/extract`) → *IF status = ok* →
*QuickBooks / Google Sheets*, with everything else routed to a Slack review channel.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

15 tests: real text extraction and **real OCR** on the sample files, every validation rule, duplicate
detection, failure handling, CSV/Excel/JSON export, the upload endpoint, and the request format sent to
OpenAI and Claude (LLM calls are mocked). GitHub Actions installs Tesseract and runs the suite on every push.

To regenerate the sample invoices: `python examples/make_sample_invoices.py`.

## Project structure

```
invoice_pipeline/
  reader.py      PDF text layer, OCR fallback for scans and images
  extractor.py   OpenAI (structured outputs) and Claude (tool use) extractors
  schema.py      Pydantic models: Invoice, LineItem, ExtractionResult
  validate.py    accounting and sanity checks
  pipeline.py    process a file or folder, duplicate detection
  export.py      CSV, Excel, JSON, Google Sheets
  api.py         FastAPI upload endpoint
  cli.py         invoice-extract command
examples/        sample invoices and the script that generates them
tests/           pytest suite
```

## License

MIT © Zohaib Tariq
