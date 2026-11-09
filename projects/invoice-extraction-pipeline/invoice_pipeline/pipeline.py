"""Process one invoice or a whole folder."""

from __future__ import annotations

import logging
from pathlib import Path

from .extractor import ExtractionError, Extractor
from .reader import SUPPORTED, UnreadableFileError, read_text
from .schema import ExtractionResult
from .validate import check_invoice

log = logging.getLogger("invoice_pipeline")


def process_file(path: Path, extractor: Extractor) -> ExtractionResult:
    try:
        text, source = read_text(path)
    except UnreadableFileError as exc:
        return ExtractionResult(file=path.name, status="failed", issues=[str(exc)])

    try:
        invoice = extractor.extract(text)
    except ExtractionError as exc:
        return ExtractionResult(file=path.name, status="failed", text_source=source, issues=[str(exc)])

    issues = check_invoice(invoice)
    return ExtractionResult(
        file=path.name,
        status="needs_review" if issues else "ok",
        text_source=source,
        invoice=invoice,
        issues=issues,
    )


def process_folder(folder: Path, extractor: Extractor) -> list[ExtractionResult]:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in SUPPORTED)
    results = []
    seen: dict[tuple[str, str], str] = {}
    for path in files:
        result = process_file(path, extractor)
        if result.invoice:
            key = (result.invoice.vendor_name.strip().lower(), result.invoice.invoice_number.strip().lower())
            if key in seen:
                result.issues.append(f"Possible duplicate of {seen[key]} (same vendor and invoice number)")
                result.status = "needs_review"
            else:
                seen[key] = path.name
        log.info("%s: %s %s", path.name, result.status, "; ".join(result.issues))
        results.append(result)
    return results
