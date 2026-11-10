import os
import tempfile
from pathlib import Path

import streamlit as st

from lib import embed, llm, ui

repo = ui.project_path("pdf-rag-knowledge-assistant")
import sys  # noqa: E402

sys.path.insert(0, str(repo / "src"))
from langchain_core.vectorstores import InMemoryVectorStore  # noqa: E402
from pdf_rag.config import Settings  # noqa: E402
from pdf_rag.generation.llm_client import generate_answer  # noqa: E402
from pdf_rag.ingestion.chunker import chunk_pages  # noqa: E402
from pdf_rag.ingestion.pdf_loader import load_pdf_pages  # noqa: E402
from pdf_rag.retrieval.retriever import RetrievedChunk  # noqa: E402

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "northwind_handbook.pdf"
QUESTIONS = ["How many days can I work from home?", "What is the meal allowance when travelling in Asia?",
             "Can I carry unused leave into next year?", "What is the company's stock option policy?"]


def settings() -> Settings:
    # The project's generator uses the OpenAI SDK, which reads OPENAI_BASE_URL: point it at Groq.
    os.environ["OPENAI_BASE_URL"] = llm.GROQ_BASE_URL
    return Settings(openai_api_key=llm.require_key(), openai_chat_model=llm.SMART, primary_llm_provider="openai",
                    retrieval_top_k=4)


def store(cfg: Settings) -> InMemoryVectorStore:
    # The project stores vectors in pgvector; this free host can't load pgvector, so the demo keeps them in memory.
    if "pdf_store" not in st.session_state:
        st.session_state.pdf_store = InMemoryVectorStore(embed.LangChainEmbeddings())
        st.session_state.pdf_files = []
    return st.session_state.pdf_store


def ingest(cfg: Settings, path: Path) -> int:
    """Same steps as the project's ingestion pipeline: pages → chunks → embeddings → pgvector."""
    chunks = chunk_pages(load_pdf_pages(path), source_file=path.name, chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap)
    store(cfg).add_texts(texts=[c.text for c in chunks], metadatas=[
        {"chunk_id": c.chunk_id, "source_file": c.source_file, "page_number": c.page_number, "chunk_index": c.chunk_index}
        for c in chunks])
    st.session_state.pdf_files.append((path.name, len(chunks)))
    return len(chunks)


ui.header(
    "PDF RAG Knowledge Assistant",
    "Upload PDFs and ask questions about them. Answers come only from your documents, with the file and page for "
    "every claim, and the assistant says so when the documents don't cover a question.",
    "pdf-rag-knowledge-assistant",
    flow=["Upload PDF", "Extract pages", "Chunk + embed", "pgvector similarity search", "Grounded answer with page citations"],
    note="Your PDFs stay private to this browser session and are thrown away when the app restarts. "
         "(The project stores vectors in PostgreSQL with pgvector; this free demo keeps them in memory.)",
)

try:
    cfg = settings()
except Exception as exc:
    llm.friendly_error(exc)
    st.stop()
store(cfg)
c1, c2 = st.columns([3, 2])
with c1:
    up = st.file_uploader("Upload a PDF", type=["pdf"])
    if up and up.name not in [f for f, _ in st.session_state.pdf_files]:
        path = Path(tempfile.mkdtemp()) / up.name
        path.write_bytes(up.getvalue())
        with st.spinner("Reading, chunking and embedding…"):
            try:
                st.success(f"Added {up.name}: {ingest(cfg, path)} chunks")
            except Exception as exc:
                st.error(f"Couldn't read that PDF: {exc}")
with c2:
    if SAMPLE.name not in [f for f, _ in st.session_state.pdf_files] and st.button("Use the sample: employee handbook (3 pages)"):
        with st.spinner("Reading, chunking and embedding…"):
            ingest(cfg, SAMPLE)
    for name, n in st.session_state.pdf_files:
        st.caption(f"📄 {name} · {n} chunks")

if st.session_state.pdf_files:
    q = st.text_input("Ask a question", value=st.pills("Examples", QUESTIONS) or "")
    if st.button("Ask", type="primary") and q.strip():
        try:
            with st.spinner("Searching your documents and writing a grounded answer…"):
                hits = store(cfg).similarity_search_with_score(q, k=cfg.retrieval_top_k)
                chunks = [RetrievedChunk(d.page_content, d.metadata.get("source_file", "?"), d.metadata.get("page_number", -1), s)
                          for d, s in hits]
                st.session_state.pdf_answer = (generate_answer(q, chunks, cfg), chunks)
        except Exception as exc:
            llm.friendly_error(exc)
    if st.session_state.get("pdf_answer"):
        answer, chunks = st.session_state.pdf_answer
        st.markdown(answer)
        with st.expander(f"Retrieved passages ({len(chunks)})"):
            for c in chunks:
                st.markdown(f"**{c.source_file}, page {c.page_number}** · relevance {c.score:.2f}\n\n> {c.text[:400]}")
else:
    st.info("Upload a PDF or load the sample to start.")
ui.footer()
