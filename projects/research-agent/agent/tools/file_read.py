"""Local file ingestion tool: PDF via PyMuPDF, everything else as text."""

from __future__ import annotations

from pathlib import Path

import pymupdf  # PyMuPDF (the modern import name for `fitz`)
from pydantic import BaseModel, Field

from ..config import FILE_READ_BASE_DIR, FILE_READ_MAX_CHARS
from .base import Tool


class FileReadArgs(BaseModel):
    path: str = Field(..., description="Path to a .txt or .pdf file, relative to the project root")
    max_chars: int = Field(default=FILE_READ_MAX_CHARS, description="Truncate output to this many characters")


class FileReadTool(Tool):
    name = "file_read"
    description = (
        "Read a local file so its contents can be reasoned over. "
        "Input: a file path (.pdf is parsed with PyMuPDF, other files are read as text)."
    )
    args_schema = FileReadArgs

    def run(self, args: FileReadArgs) -> str:  # type: ignore[override]
        resolved = self._safe_resolve(args.path)
        if isinstance(resolved, str):
            return resolved  # error message

        if not resolved.exists() or not resolved.is_file():
            return f"file_read error: no such file '{args.path}'"

        try:
            if resolved.suffix.lower() == ".pdf":
                text = self._read_pdf(resolved)
            else:
                text = resolved.read_text(encoding="utf-8-sig", errors="replace")
        except Exception as exc:  # noqa: BLE001 - surface any parse failure as an observation
            return f"file_read error: {exc}"

        limit = max(500, args.max_chars)
        if len(text) > limit:
            text = text[:limit] + "\n...[truncated]"
        return text or "file_read: file is empty"

    @staticmethod
    def _safe_resolve(raw: str) -> "Path | str":
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = FILE_READ_BASE_DIR / candidate
        candidate = candidate.resolve()
        try:
            candidate.relative_to(FILE_READ_BASE_DIR)
        except ValueError:
            return (
                f"file_read error: '{raw}' is outside the allowed directory "
                f"({FILE_READ_BASE_DIR})"
            )
        return candidate

    @staticmethod
    def _read_pdf(path: Path) -> str:
        parts: list[str] = []
        with pymupdf.open(path) as doc:
            for page in doc:
                parts.append(page.get_text())
        return "\n".join(parts)
