"""Pydantic request/response models for the API."""

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    file: str
    pages_processed: int
    chunks_created: int


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class Citation(BaseModel):
    source_file: str
    page_number: int
    relevance_score: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]


class HealthResponse(BaseModel):
    status: str
    version: str


class ErrorResponse(BaseModel):
    error: str
    detail: str
