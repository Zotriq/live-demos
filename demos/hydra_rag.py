import dataclasses
import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

from lib import embed, llm, ui

repo = ui.project_path("hydra-rag")
for name in [m for m in sys.modules if m in ("src", "utilities") or m.startswith(("src.", "utilities."))]:
    if not str(getattr(sys.modules[name], "__file__", "") or "").startswith(str(repo)):
        del sys.modules[name]  # another project's "src"/"utilities" must not shadow Hydra's
if llm.groq_key():
    os.environ.setdefault("GROQ_API_KEY", llm.groq_key())  # Hydra's vision loader reads it

import utilities.session as session_mod  # noqa: E402

session_mod.DATA_ROOT = str(Path(tempfile.gettempdir()) / "hydra-data")
from src.config import rag_settings  # noqa: E402
from src.embeddings.embedder import BGE_QUERY_PREFIX, Embedder  # noqa: E402
from src.embeddings.vector_store import InMemoryVectorStore  # noqa: E402
from src.pipeline.index import Indexer  # noqa: E402
from src.pipeline.ingest import ingest_files, ingest_url  # noqa: E402
from src.pipeline.rag_chain import RagChain  # noqa: E402
from src.retrieval.reranker import Reranker  # noqa: E402

SAMPLE = ui.ROOT / "assets" / "northwind_handbook.pdf"
TYPES = ["pdf", "docx", "pptx", "xlsx", "xls", "csv", "txt", "md", "html", "png", "jpg", "jpeg", "webp"]
# Smaller open models than production (bge-large + bge-reranker-large) so the free server can run them.
SETTINGS = dataclasses.replace(rag_settings, embedding_dimension=embed.DIM, min_score=0.45)


class SmallEmbedder(Embedder):
    dimension = embed.DIM

    def embed_documents(self, texts):
        return embed.embed(texts) if texts else []

    def embed_query(self, text):
        return embed.embed([BGE_QUERY_PREFIX + text])[0]


class SmallReranker(Reranker):
    """MiniLM cross-encoder via fastembed (ONNX, CPU); falls back to vector order."""

    def __init__(self):
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self.model = TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2")
        except Exception:
            self.model = None

    def rerank(self, question, matches, top_n):
        if not matches:
            return []
        if self.model is None:
            return [(m, m.score) for m in matches[:top_n]]
        scores = list(self.model.rerank(question, [m.metadata.get("text", "") for m in matches]))
        return sorted(zip(matches, map(float, scores)), key=lambda p: p[1], reverse=True)[:top_n]


def groq_answer(system: str, user: str) -> str:
    from openai import OpenAI

    r = OpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL).chat.completions.create(
        model=llm.SMART, temperature=0, reasoning_effort="low", max_tokens=4096,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return r.choices[0].message.content or ""


@st.cache_resource(show_spinner="Loading the embedding and reranking models…")
def engine():
    store, embedder = InMemoryVectorStore(), SmallEmbedder()
    return (Indexer(embedder=embedder, vector_store=store, settings=SETTINGS, confirm_poll_s=0),
            RagChain(embedder=embedder, vector_store=store, reranker=SmallReranker(), llm=groq_answer,
                     settings=SETTINGS, llm_wait_max=4))


def add(batch) -> None:
    st.session_state.hydra_session = batch.session_id
    indexer, _ = engine()
    if batch.error:
        st.error(batch.error)
    indexed = {r.doc_id: r for r in indexer.index_batch(batch)}
    for f in batch.files:
        idx = indexed.get(f.doc_id)
        note = f.reason or (idx.reason if idx else None) or ""
        st.session_state.hydra_files.append((f.source, f.status, note, f.element_count))


ui.header(
    "Hydra RAG",
    "Chat with almost any document: PDFs, Word, PowerPoint, Excel and CSV, plain text, images (described by a "
    "vision model) and web pages. Every answer cites the file and location it came from, and the assistant says so "
    "when your documents don't cover the question.",
    None,
    flow=["Files or a URL", "Format-aware loaders + vision for images", "Chunk + embed", "Vector search + rerank", "Answer with citations"],
    note="Built with Ahmed Javed. Production uses Pinecone, bge-large and bge-reranker-large; this free demo runs the "
         "same pipeline with an in-memory store and smaller open models. Files stay private to your session.",
)
st.markdown('<div class="demo-links" style="margin-top:-6px"><a href="https://github.com/ahmedjavedcodes/hydra-rag" '
            'target="_blank">Hydra RAG repository</a></div>', unsafe_allow_html=True)
st.session_state.setdefault("hydra_files", [])

c1, c2 = st.columns([3, 2])
with c1:
    ups = st.file_uploader("Upload files", type=TYPES, accept_multiple_files=True)
    if ups and st.button("Add these files", type="primary"):
        folder = Path(tempfile.mkdtemp())
        paths = []
        for up in ups:
            (folder / up.name).write_bytes(up.getvalue())
            paths.append(str(folder / up.name))
        with st.spinner("Reading, describing images, chunking and indexing…"):
            try:
                add(ingest_files(paths, session_id=st.session_state.get("hydra_session")))
            except Exception as exc:
                llm.friendly_error(exc)
    url = st.text_input("…or add a web page", placeholder="https://…")
    if url and st.button("Add page"):
        with st.spinner("Fetching and indexing the page…"):
            try:
                add(ingest_url(url, session_id=st.session_state.get("hydra_session")))
            except Exception as exc:
                llm.friendly_error(exc)
with c2:
    if st.button("Use the sample: employee handbook (PDF)"):
        with st.spinner("Indexing the sample…"):
            add(ingest_files([str(SAMPLE)], session_id=st.session_state.get("hydra_session")))
    for name, status, note, elements in st.session_state.hydra_files:
        label = "indexed" if status == "ok" else status
        st.caption(f"📄 {Path(str(name)).name} · {label} · {elements} elements" + (f" · {note}" if note else ""))

if st.session_state.get("hydra_session"):
    q = st.text_input("Ask a question about your documents")
    if st.button("Ask") and q.strip():
        try:
            with st.spinner("Searching, reranking and answering…"):
                st.session_state.hydra_answer = engine()[1].ask(st.session_state.hydra_session, q)
        except Exception as exc:
            llm.friendly_error(exc)
    a = st.session_state.get("hydra_answer")
    if a:
        st.markdown(a.answer)
        for s in a.sources:
            where = f", {s.location}" if s.location else ""
            st.caption(f"[{s.index}] {s.filename or s.source_url}{where}: “{s.passage[:150]}…”")
        for n in a.notes:
            st.caption(n)
ui.footer()
