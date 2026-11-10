"""
End-to-end ingestion pipeline: PDF file -> pages -> chunks -> embeddings -> vector store.

This is the orchestration layer used by both the API upload endpoint and the
standalone CLI ingestion script, so behavior stays identical between the two
entry points.
"""

from pathlib import Path

from pdf_rag.config import Settings
from pdf_rag.core.logging_config import get_logger
from pdf_rag.embeddings.embedder import get_embeddings_client
from pdf_rag.ingestion.chunker import chunk_pages
from pdf_rag.ingestion.pdf_loader import load_pdf_pages
from pdf_rag.vectorstore.pgvector_store import get_vector_store

logger = get_logger(__name__)


def ingest_pdf(file_path: str | Path, settings: Settings) -> dict:
    """
    Ingest a single PDF: extract text, chunk it, embed the chunks, and
    persist them in the vector store.

    Returns a summary dict describing what was ingested (useful for the API
    response and for CLI output).
    """
    path = Path(file_path)

    pages = load_pdf_pages(path)
    chunks = chunk_pages(
        pages,
        source_file=path.name,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    if not chunks:
        raise ValueError(f"No chunks produced for '{path.name}'.")

    embeddings_client = get_embeddings_client(settings)
    vector_store = get_vector_store(settings, embeddings_client)

    texts = [chunk.text for chunk in chunks]
    metadatas = [
        {
            "chunk_id": chunk.chunk_id,
            "source_file": chunk.source_file,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
        }
        for chunk in chunks
    ]

    vector_store.add_texts(texts=texts, metadatas=metadatas)

    logger.info("ingestion_complete", file=path.name, chunks=len(chunks), pages=len(pages))

    return {
        "file": path.name,
        "pages_processed": len(pages),
        "chunks_created": len(chunks),
    }
