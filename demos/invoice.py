import json
import tempfile
from pathlib import Path

import pandas as pd
import pdfplumber
import streamlit as st

from lib import llm, ui

repo = ui.project_path("invoice-extraction-pipeline")
from invoice_pipeline.export import export_excel  # noqa: E402
from invoice_pipeline.extractor import OpenAIExtractor  # noqa: E402
from invoice_pipeline.pipeline import process_file  # noqa: E402
from invoice_pipeline.reader import SUPPORTED  # noqa: E402

SAMPLES = {p.name: p for p in sorted((repo / "examples" / "sample_invoices").glob("*.pdf"))}
LABELS = {
    "northwind_INV-2041.pdf": "Northwind (normal PDF)",
    "bluepeak_BP-778.pdf": "BluePeak (PDF with a maths mistake)",
    "scanned_ACME-5512.pdf": "ACME (scanned image, needs OCR)",
}
STATUS = {"ok": ("success", "All checks passed"), "needs_review": ("warning", "Needs review"), "failed": ("error", "Failed")}

ui.header(
    "Invoice Extraction Pipeline",
    "Reads invoice PDFs and scans, pulls out the vendor, dates, line items and totals into a strict schema, then "
    "double-checks the maths so wrong totals are flagged before they reach accounting.",
    "invoice-extraction-pipeline",
    flow=["PDF or scan", "Text layer, or OCR if scanned", "LLM → strict JSON schema", "Totals & dates checked", "Excel / JSON / API"],
    note="Uploads are processed in memory for this demo and not stored.",
)

source = st.radio("Invoice", ["Use a sample", "Upload my own"], horizontal=True)
path = None
if source == "Use a sample":
    name = st.pills("Sample", list(SAMPLES), format_func=lambda n: LABELS.get(n, n), default=list(SAMPLES)[0])
    path = SAMPLES.get(name)
else:
    up = st.file_uploader("Invoice (PDF or image)", type=[s.lstrip(".") for s in SUPPORTED])
    if up:
        tmp = Path(tempfile.mkdtemp()) / up.name
        tmp.write_bytes(up.getvalue())
        path = tmp

if path:
    left, right = st.columns([2, 3])
    with left:
        if path.suffix.lower() == ".pdf":
            with pdfplumber.open(path) as pdf:
                st.image(pdf.pages[0].to_image(resolution=80).original, caption=path.name)
        else:
            st.image(str(path), caption=path.name)
    with right:
        if st.button("Extract invoice", type="primary"):
            extractor = OpenAIExtractor(api_key=llm.require_key(), model=llm.SMART, base_url=llm.GROQ_BASE_URL)
            try:
                with st.spinner("Reading the file and extracting…"):
                    st.session_state.invoice_result = process_file(path, extractor)
            except Exception as exc:
                llm.friendly_error(exc)
        result = st.session_state.get("invoice_result")
        if result and result.file == path.name:
            kind, label = STATUS[result.status]
            getattr(st, kind)(f"**{label}** · text from {'OCR' if result.text_source == 'ocr' else 'the PDF text layer'}")
            for issue in result.issues:
                st.markdown(f"- {issue}")
            inv = result.invoice
            if inv:
                a, b, c = st.columns(3)
                a.metric("Vendor", inv.vendor_name)
                b.metric("Invoice", inv.invoice_number)
                c.metric("Total", f"{inv.total:,.2f} {inv.currency}")
                st.markdown(
                    f"**Date:** {inv.invoice_date} · **Due:** {inv.due_date or '—'} · **Bill to:** {inv.bill_to or '—'} · "
                    f"**Tax ID:** {inv.vendor_tax_id or '—'} · **Subtotal:** {inv.subtotal if inv.subtotal is not None else '—'} · **Tax:** {inv.tax}"
                )
                st.dataframe(pd.DataFrame([li.model_dump() for li in inv.line_items]).astype(str), width="stretch", hide_index=True)
                out = Path(tempfile.mkdtemp())
                d1, d2 = st.columns(2)
                d1.download_button("Download Excel", export_excel([result], out).read_bytes(), "invoices.xlsx")
                d2.download_button("Download JSON", json.dumps(result.model_dump(mode="json"), indent=2), "invoice.json")
ui.footer()
