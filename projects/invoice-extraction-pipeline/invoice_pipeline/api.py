"""HTTP API: upload an invoice, get structured JSON back (for n8n, Make, Zapier or your app)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile

from .cli import make_extractor
from .extractor import Extractor
from .pipeline import process_file
from .reader import SUPPORTED
from .schema import ExtractionResult

app = FastAPI(title="Invoice Extraction API", version="0.1.0")

MAX_BYTES = 15 * 1024 * 1024


def get_extractor() -> Extractor:
    return make_extractor(os.getenv("LLM_PROVIDER", "openai"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractionResult)
async def extract(file: UploadFile, extractor: Extractor = Depends(get_extractor)) -> ExtractionResult:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(415, f"Unsupported file type '{suffix}'. Use PDF, PNG or JPG.")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 15 MB")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / Path(file.filename).name
        path.write_bytes(data)
        return process_file(path, extractor)
