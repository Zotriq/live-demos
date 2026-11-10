"""Document ingestion endpoints."""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from pdf_rag.api.dependencies import require_api_key, settings_dependency
from pdf_rag.api.schemas import ErrorResponse, IngestResponse
from pdf_rag.config import Settings
from pdf_rag.core.exceptions import DocumentProcessingError, FileTooLargeError, UnsupportedFileTypeError
from pdf_rag.core.logging_config import get_logger
from pdf_rag.ingestion.pipeline import ingest_pdf

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)

UPLOAD_DIR = Path("data/uploads")


@router.post(
    "/upload",
    response_model=IngestResponse,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_key)],
)
async def upload_document(
    file: UploadFile,
    settings: Settings = Depends(settings_dependency),
) -> IngestResponse:
    """
    Upload a PDF, extract text, chunk it, embed it, and store it in the
    vector database so it becomes queryable via /chat/ask.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("Only PDF files are supported.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    destination = UPLOAD_DIR / safe_name

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    size = 0
    try:
        with destination.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise FileTooLargeError(
                        f"File exceeds max upload size of {settings.max_upload_size_mb} MB."
                    )
                buffer.write(chunk)

        result = ingest_pdf(destination, settings)
        return IngestResponse(**result)

    except (FileTooLargeError, UnsupportedFileTypeError, DocumentProcessingError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        # Uploaded raw files are transient; only chunks/embeddings persist.
        if destination.exists():
            destination.unlink(missing_ok=True)
