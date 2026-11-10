"""
FastAPI application entrypoint.

Run locally with:
    uvicorn src.pdf_rag.main:app --reload

Wires together: CORS, structured logging, global exception handling,
health check, and the documents/chat routers.
"""

import time
from collections import defaultdict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pdf_rag.api.routes import chat, documents
from pdf_rag.api.schemas import HealthResponse
from pdf_rag.config import get_settings
from pdf_rag.core.exceptions import PDFRagError
from pdf_rag.core.logging_config import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

APP_VERSION = "0.1.0"

app = FastAPI(
    title="PDF RAG Knowledge Assistant",
    description="Retrieval-Augmented Generation API for question-answering over uploaded PDF documents.",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# --- Minimal in-memory rate limiter (per-process) ---
# For multi-instance deployments, replace with a Redis-backed limiter
# (see docs/deployment.md).
_request_log: dict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - 60
    _request_log[client_ip] = [t for t in _request_log[client_ip] if t > window_start]

    if len(_request_log[client_ip]) >= settings.rate_limit_per_minute:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "rate_limited", "detail": "Too many requests. Please slow down."},
        )

    _request_log[client_ip].append(now)
    return await call_next(request)


@app.exception_handler(PDFRagError)
async def pdf_rag_exception_handler(request: Request, exc: PDFRagError):
    logger.error("unhandled_pdf_rag_error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": exc.__class__.__name__, "detail": str(exc)},
    )


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version=APP_VERSION)


app.include_router(documents.router)
app.include_router(chat.router)
