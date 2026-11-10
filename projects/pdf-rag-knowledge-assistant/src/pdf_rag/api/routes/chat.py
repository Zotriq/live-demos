"""Chat / question-answering endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status

from pdf_rag.api.dependencies import require_api_key, settings_dependency
from pdf_rag.api.schemas import ChatRequest, ChatResponse, Citation, ErrorResponse
from pdf_rag.config import Settings
from pdf_rag.core.exceptions import GenerationError, RetrievalError
from pdf_rag.core.logging_config import get_logger
from pdf_rag.generation.llm_client import generate_answer
from pdf_rag.retrieval.retriever import retrieve_relevant_chunks

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


@router.post(
    "/ask",
    response_model=ChatResponse,
    responses={422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_key)],
)
async def ask_question(
    request: ChatRequest,
    settings: Settings = Depends(settings_dependency),
) -> ChatResponse:
    """
    Answer a question using retrieval-augmented generation over previously
    ingested PDF documents.
    """
    try:
        chunks = retrieve_relevant_chunks(request.question, settings, top_k=request.top_k)
    except RetrievalError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if not chunks:
        return ChatResponse(
            answer=(
                "I couldn't find relevant information in the uploaded documents to answer "
                "that question. Try rephrasing, or upload a document that covers this topic."
            ),
            citations=[],
        )

    try:
        answer = generate_answer(request.question, chunks, settings)
    except GenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    citations = [
        Citation(source_file=c.source_file, page_number=c.page_number, relevance_score=round(c.score, 4))
        for c in chunks
    ]
    return ChatResponse(answer=answer, citations=citations)
