import uuid

import psycopg
import streamlit as st
from fastapi.testclient import TestClient
from openai import OpenAI

from lib import embed, llm, pg, ui, vector_fallback

repo = ui.project_path("multitenant-rag-saas")
import rag_saas.db as rag_db  # noqa: E402
from rag_saas.api import create_app  # noqa: E402
from rag_saas.db import Store, create_tenant  # noqa: E402
from rag_saas.providers import ANSWER_PROMPT  # noqa: E402

TENANTS = {
    "Acme Clinics": [
        ("Leave policy", "Acme Clinics staff get 24 days of paid annual leave. Leave requests must be approved by the "
         "clinic manager at least two weeks in advance. Unused leave of up to 5 days can be carried into the next year."),
        ("Patient refunds", "Acme Clinics refunds a cancelled appointment in full if the patient cancels at least 24 hours "
         "before. Later cancellations are charged a fee of $40. Refunds are paid back to the original card within 5 days."),
        ("Confidential: 2027 plan", "CONFIDENTIAL. Acme Clinics will open three new branches in 2027, in Austin, Denver and "
         "Phoenix, with a budget of $4.2 million. Do not share outside the leadership team."),
    ],
    "Bolt Logistics": [
        ("Leave policy", "Bolt Logistics drivers get 18 days of paid leave per year. Leave in December needs approval from "
         "the operations director because it is peak season."),
        ("Damaged parcels", "If a parcel arrives damaged, Bolt Logistics customers must report it within 48 hours with photos. "
         "Claims are reviewed within 3 business days and paid up to the declared value."),
        ("Confidential: pricing", "CONFIDENTIAL. Bolt Logistics will raise express delivery prices by 12% on 1 March. "
         "The largest client, Northwind, gets a locked rate until June."),
    ],
}


class Embedder:
    """Local open-source embeddings shared by the RAG demos (lib/embed.py)."""
    dim = embed.DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        return embed.embed(texts)


class GroqGenerator:
    def answer(self, question: str, sources: list[str]) -> str:
        if not sources:
            return "I don't know. None of your company's documents cover that."
        numbered = "\n\n".join(f"[{i}] {s}" for i, s in enumerate(sources, 1))
        r = OpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL).chat.completions.create(
            model=llm.FAST, temperature=0,
            messages=[{"role": "user", "content": ANSWER_PROMPT.format(sources=numbered, question=question)}])
        return r.choices[0].message.content or ""


# On this free host pgvector can't load (see lib/vector_fallback.py), so vectors are float arrays.
rag_db.register_vector = vector_fallback.register


@st.cache_resource(show_spinner="Starting PostgreSQL and loading the embedding model…")
def platform():
    base = pg.full()
    with psycopg.connect(base, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = 'rag'").fetchone():
            conn.execute("CREATE DATABASE rag")
    admin = base.replace("dbname=postgres", "dbname=rag")
    embedder = Embedder()
    # The project's schema; gen_random_uuid() is built into PostgreSQL 13+, so pgcrypto isn't needed here.
    schema = vector_fallback.adapt_schema((repo / "rag_saas" / "schema.sql").read_text(), embedder.dim)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(schema.replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;", ""))
    host = admin.split("host=")[1].split()[0]
    return admin, f"host={host} user=rag_app dbname=rag", embedder


def session():
    if "rag" not in st.session_state:
        admin, app_url, embedder = platform()
        client = TestClient(create_app(Store(app_url), embedder, GroqGenerator(), admin_url=admin, admin_token="admin"))
        tenants = {}
        for name, docs in TENANTS.items():
            tid, key = create_tenant(admin, name)
            for title, text in docs:
                r = client.post("/documents", data={"title": title, "text": text}, headers={"X-API-Key": key})
                r.raise_for_status()
            tenants[name] = {"id": str(tid), "key": key}
        st.session_state.rag = {"client": client, "tenants": tenants, "app_url": app_url}
    return st.session_state.rag


ui.header(
    "Multi-tenant RAG SaaS",
    "A chat-with-your-documents backend for many companies at once. Each company signs in with its own API key, and "
    "PostgreSQL row-level security makes the **database itself** refuse to return another company's rows, even if "
    "the application code had a bug.",
    "multitenant-rag-saas",
    flow=["API key → tenant", "SET LOCAL app.tenant_id", "pgvector search (RLS applied)", "Answer with citations", "Other tenants: 0 rows"],
    note="Two demo companies were just created for you, each with its own documents (including one marked confidential). "
         "On this free host the pgvector extension can't load, so embeddings are stored as float arrays with an exact "
         "cosine-distance operator; the row-level security is exactly the project's.",
)
s = session()
me = st.radio("Signed in as", list(s["tenants"]), horizontal=True)
other = [n for n in s["tenants"] if n != me][0]
key = s["tenants"][me]["key"]
headers = {"X-API-Key": key}
st.caption(f"API key for {me}: `{key[:10]}…` (only its SHA-256 hash is stored)")

ask_tab, docs_tab, attack_tab = st.tabs(["Ask a question", "Documents", f"Try to read {other}'s data"])
with ask_tab:
    examples = ["How many days of paid leave do staff get?", "What is the refund policy?",
                f"What is in {other}'s confidential plan?", "Are prices going up?"]
    q = st.text_input("Question", value=st.pills("Examples", examples, key=f"q_{me}") or "")
    if st.button("Ask", type="primary") and len(q) >= 3:
        try:
            with st.spinner("Searching only your company's documents…"):
                r = s["client"].post("/query", json={"question": q, "top_k": 3}, headers=headers).json()
            st.markdown(r["answer"])
            for c in r["citations"]:
                st.caption(f"[{c['n']}] {c['title']} · similarity {c['score']:.2f}: “{c['excerpt'][:160]}…”")
        except Exception as exc:
            llm.friendly_error(exc)

with docs_tab:
    for d in s["client"].get("/documents", headers=headers).json():
        st.markdown(f"- **{d['title']}** · {d['chunks']} chunk(s)")
    with st.form("upload", clear_on_submit=True):
        title = st.text_input("Add a document: title")
        text = st.text_area("Text", height=100)
        if st.form_submit_button("Upload") and text.strip():
            r = s["client"].post("/documents", data={"title": title or "Untitled", "text": text}, headers=headers)
            st.success(f"Stored as {r.json()['chunks']} chunk(s)") if r.ok else st.error(r.text)

with attack_tab:
    victim = s["tenants"][other]["id"]
    st.markdown(f"Each check runs as the app's real database role (`rag_app`) while signed in as **{me}**.")
    if st.button("Run the isolation checks", type="primary"):
        results = []
        with psycopg.connect(s["app_url"]) as conn:
            n = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
            results.append(("Query with no tenant set (a forgotten WHERE clause)", f"{n} rows visible"))
            conn.rollback()
            with conn.transaction():
                conn.execute("SELECT set_config('app.tenant_id', %s, true)", (s["tenants"][me]["id"],))
                n = conn.execute("SELECT count(*) FROM documents WHERE tenant_id = %s", (victim,)).fetchone()[0]
                results.append((f"Ask for {other}'s rows by tenant_id directly", f"{n} rows returned"))
            try:
                with conn.transaction():
                    conn.execute("SELECT set_config('app.tenant_id', %s, true)", (s["tenants"][me]["id"],))
                    conn.execute("INSERT INTO documents (tenant_id, title) VALUES (%s, 'planted')", (victim,))
                results.append((f"Plant a document inside {other}'s account", "⚠️ allowed"))
            except psycopg.Error as exc:
                results.append((f"Plant a document inside {other}'s account", f"blocked: {exc.diag.message_primary}"))
            try:
                with conn.transaction():
                    conn.execute("SET LOCAL row_security = off")
                    conn.execute("SELECT count(*) FROM chunks")
                results.append(("Switch row-level security off", "⚠️ allowed"))
            except psycopg.Error as exc:
                results.append(("Switch row-level security off", f"blocked: {exc.diag.message_primary}"))
        their_doc = s["client"].get("/documents", headers={"X-API-Key": s["tenants"][other]["key"]}).json()[0]["id"]
        r = s["client"].delete(f"/documents/{their_doc}", headers=headers)
        results.append((f"Delete {other}'s document through the API", f"HTTP {r.status_code} {r.json().get('detail', '')}"))
        r = s["client"].get("/documents", headers={"X-API-Key": "rag_made_up_key"})
        results.append(("Use a made-up API key", f"HTTP {r.status_code} {r.json().get('detail', '')}"))
        st.table([{"Attack": a, "Result": b} for a, b in results])
ui.footer()
