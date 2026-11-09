"""Get text out of an invoice file: embedded PDF text first, OCR only when needed."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
SUPPORTED = IMAGE_TYPES | {".pdf"}

# A real text layer has plenty of characters; a scanned PDF has none or a few stray ones.
MIN_TEXT_CHARS = 40


class UnreadableFileError(ValueError):
    pass


def _ocr_image(image) -> str:
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - depends on install
        raise UnreadableFileError("OCR needs `pip install pytesseract` and the Tesseract binary") from exc
    return pytesseract.image_to_string(image)


def read_text(path: Path, *, ocr_resolution: int = 300) -> tuple[str, str]:
    """Return (text, source) where source is "pdf_text" or "ocr"."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise UnreadableFileError(f"Unsupported file type {suffix}")

    if suffix in IMAGE_TYPES:
        from PIL import Image

        with Image.open(path) as img:
            return _ocr_image(img), "ocr"

    with pdfplumber.open(path) as pdf:
        text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        if len(text.strip()) >= MIN_TEXT_CHARS:
            return text, "pdf_text"
        # Scanned PDF: render each page and OCR it.
        pages = [_ocr_image(page.to_image(resolution=ocr_resolution).original) for page in pdf.pages]
    text = "\n".join(pages)
    if not text.strip():
        raise UnreadableFileError("No text found, even with OCR")
    return text, "ocr"
