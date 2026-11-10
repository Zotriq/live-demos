"""
Prompt construction for the RAG answer generation step.

Prompts are intentionally centralized here (mirrored as plain text in
prompts/) so they can be reviewed, versioned, and evaluated independent of
application code.
"""

from pdf_rag.retrieval.retriever import RetrievedChunk

SYSTEM_PROMPT = (
    "You are a careful documentation assistant. Answer the user's question "
    "using ONLY the provided context excerpts from their uploaded PDF documents. "
    "If the context does not contain enough information to answer confidently, "
    "say so explicitly rather than guessing. Always cite the source file and "
    "page number for any claim you make, in the format [source_file, p.N]. "
    "Do not use outside knowledge that is not present in the context."
)


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No relevant context was found in the uploaded documents."

    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[Excerpt {i} - {chunk.source_file}, p.{chunk.page_number}]\n{chunk.text}"
        )
    return "\n\n".join(parts)


def build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context = build_context_block(chunks)
    return (
        f"Context excerpts:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the context above. Cite sources as [source_file, p.N]."
    )
