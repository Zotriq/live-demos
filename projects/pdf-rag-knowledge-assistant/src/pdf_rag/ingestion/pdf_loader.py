"""
PDF loading and text extraction.

Wraps pypdf so the rest of the application depends on a stable interface
instead of a third-party library directly (easy to swap for a different
parser later, e.g. unstructured.io, without touching downstream code).
"""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from pdf_rag.core.exceptions import DocumentProcessingError
from pdf_rag.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PageContent:
    page_number: int
    text: str


def load_pdf_pages(file_path: str | Path) -> list[PageContent]:
    """
    Extract text from every page of a PDF.

    Raises:
        DocumentProcessingError: if the file cannot be read or parsed.
    """
    path = Path(file_path)
    if not path.exists():
        raise DocumentProcessingError(f"File not found: {path}")

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # pypdf raises several distinct exception types
        raise DocumentProcessingError(f"Failed to open PDF '{path.name}': {exc}") from exc

    if reader.is_encrypted:
        raise DocumentProcessingError(
            f"PDF '{path.name}' is password-protected and cannot be ingested."
        )

    pages: list[PageContent] = []
    for index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("page_extraction_failed", page=index + 1, error=str(exc))
            text = ""
        pages.append(PageContent(page_number=index + 1, text=text))

    non_empty_pages = [p for p in pages if p.text.strip()]
    if not non_empty_pages:
        raise DocumentProcessingError(
            f"No extractable text found in '{path.name}'. "
            "The PDF may be a scanned image without OCR."
        )

    logger.info("pdf_loaded", file=path.name, pages=len(pages), pages_with_text=len(non_empty_pages))
    return pages
