"""
Retrieval layer: turns a user question into a ranked list of relevant chunks.

Kept separate from generation so retrieval quality can be tested and tuned
(top_k, score threshold, filters) independently of prompt/LLM behavior.
"""

from dataclasses import dataclass

from pdf_rag.config import Settings
from pdf_rag.core.exceptions import RetrievalError
from pdf_rag.core.logging_config import get_logger
from pdf_rag.embeddings.embedder import get_embeddings_client
from pdf_rag.vectorstore.pgvector_store import get_vector_store

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    source_file: str
    page_number: int
    score: float


def retrieve_relevant_chunks(
    question: str,
    settings: Settings,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """
    Run similarity search against the vector store for the given question.

    Raises:
        RetrievalError: if the vector store query fails.
    """
    k = top_k or settings.retrieval_top_k

    try:
        embeddings_client = get_embeddings_client(settings)
        vector_store = get_vector_store(settings, embeddings_client)
        results = vector_store.similarity_search_with_relevance_scores(question, k=k)
    except Exception as exc:
        raise RetrievalError(f"Retrieval failed for question: {exc}") from exc

    chunks = [
        RetrievedChunk(
            text=doc.page_content,
            source_file=doc.metadata.get("source_file", "unknown"),
            page_number=doc.metadata.get("page_number", -1),
            score=score,
        )
        for doc, score in results
        if score >= settings.retrieval_score_threshold
    ]

    logger.info("retrieval_complete", question_length=len(question), chunks_returned=len(chunks))
    return chunks
