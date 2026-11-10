"""
Text chunking for embedding.

Uses LangChain's RecursiveCharacterTextSplitter, which splits on paragraph
boundaries first and falls back to sentences/words, producing chunks that
respect semantic boundaries better than fixed-width slicing.
"""

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from pdf_rag.ingestion.pdf_loader import PageContent


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    page_number: int
    chunk_index: int
    source_file: str


def chunk_pages(
    pages: list[PageContent],
    source_file: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[DocumentChunk]:
    """
    Split page text into overlapping chunks suitable for embedding.

    chunk_overlap preserves context across chunk boundaries so that an answer
    spanning two chunks is not lost during retrieval.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[DocumentChunk] = []
    global_index = 0
    for page in pages:
        if not page.text.strip():
            continue
        for piece in splitter.split_text(page.text):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{source_file}::p{page.page_number}::c{global_index}",
                    text=piece,
                    page_number=page.page_number,
                    chunk_index=global_index,
                    source_file=source_file,
                )
            )
            global_index += 1

    return chunks
