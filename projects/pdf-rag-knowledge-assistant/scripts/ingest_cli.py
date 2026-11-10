#!/usr/bin/env python3
"""
Standalone CLI for ingesting PDFs without going through the API.

Usage:
    python scripts/ingest_cli.py path/to/file1.pdf path/to/file2.pdf
    python scripts/ingest_cli.py --dir path/to/pdf_folder
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdf_rag.config import get_settings  # noqa: E402
from pdf_rag.core.logging_config import configure_logging, get_logger  # noqa: E402
from pdf_rag.ingestion.pipeline import ingest_pdf  # noqa: E402

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDF files into the RAG vector store.")
    parser.add_argument("files", nargs="*", help="PDF file paths to ingest")
    parser.add_argument("--dir", help="Ingest every .pdf file found in this directory")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    targets: list[Path] = [Path(f) for f in args.files]
    if args.dir:
        targets.extend(sorted(Path(args.dir).glob("*.pdf")))

    if not targets:
        parser.error("Provide at least one PDF file or --dir with PDFs in it.")

    for path in targets:
        try:
            result = ingest_pdf(path, settings)
            print(f"OK  {result['file']}: {result['pages_processed']} pages -> {result['chunks_created']} chunks")
        except Exception as exc:
            print(f"FAIL {path}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
