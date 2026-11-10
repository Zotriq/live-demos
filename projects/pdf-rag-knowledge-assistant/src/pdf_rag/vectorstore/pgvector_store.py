"""
PostgreSQL + pgvector vector store integration.

pgvector was chosen over a managed vector DB (e.g. Pinecone) because:
- It keeps document metadata and vectors in the same PostgreSQL instance
  the rest of the application already uses, avoiding a second data store.
- It has no per-vector hosted pricing, which matters for a portfolio /
  small-business scale project (see docs/cost-analysis.md).
- It supports standard SQL filtering alongside similarity search.

Pinecone/Qdrant remain drop-in alternatives if the project needs to scale
beyond what a single PostgreSQL instance can comfortably serve.
"""

from langchain_postgres import PGVector

from pdf_rag.config import Settings
from pdf_rag.core.exceptions import VectorStoreError
from pdf_rag.core.logging_config import get_logger

logger = get_logger(__name__)

# Process-wide singleton so we don't open a new connection pool per request.
_STORE_INSTANCE: PGVector | None = None


def get_vector_store(settings: Settings, embeddings_client) -> PGVector:
    """
    Return a singleton PGVector store bound to the configured collection.

    Raises:
        VectorStoreError: if the store cannot be initialized (e.g. DB unreachable,
        pgvector extension not installed).
    """
    global _STORE_INSTANCE
    if _STORE_INSTANCE is not None:
        return _STORE_INSTANCE

    try:
        _STORE_INSTANCE = PGVector(
            embeddings=embeddings_client,
            collection_name=settings.vector_collection_name,
            connection=settings.database_url,
            use_jsonb=True,
        )
    except Exception as exc:
        raise VectorStoreError(
            f"Failed to initialize pgvector store. Ensure PostgreSQL is running and the "
            f"'vector' extension is installed (see docs/setup.md). Original error: {exc}"
        ) from exc

    logger.info("vector_store_ready", collection=settings.vector_collection_name)
    return _STORE_INSTANCE


def reset_vector_store_singleton() -> None:
    """Used by tests to force re-initialization between test cases."""
    global _STORE_INSTANCE
    _STORE_INSTANCE = None
