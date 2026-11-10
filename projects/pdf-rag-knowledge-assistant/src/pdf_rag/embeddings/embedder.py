"""
Embedding client factory.

Isolated behind a factory function so swapping embedding providers (e.g.
moving from OpenAI to a local sentence-transformers model) only requires a
change here, not in every module that consumes embeddings.
"""

from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from pdf_rag.config import Settings
from pdf_rag.core.exceptions import PDFRagError


@lru_cache
def _cached_client(provider: str, model: str, api_key: str):
    if provider == "openai":
        if not api_key:
            raise PDFRagError(
                "OPENAI_API_KEY is required for embeddings but was not set. "
                "Add it to your .env file."
            )
        return OpenAIEmbeddings(model=model, api_key=api_key)

    raise PDFRagError(f"Unsupported embedding provider: {provider}")


def get_embeddings_client(settings: Settings):
    return _cached_client(
        settings.embedding_provider,
        settings.embedding_model,
        settings.openai_api_key or "",
    )
