import uuid

import streamlit as st
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from lib import llm, ui

repo = ui.project_path("langgraph-support-agents")
from support_agents.graph import build_graph  # noqa: E402
from support_agents.llm import OpenAICompatibleLLM  # noqa: E402

INBOX = {p.stem.replace("_", " ").capitalize(): p.read_text().strip() for p in sorted((repo / "examples" / "inbox").glob("*.txt"))}
STEP = {
    "supervisor": "🧭 Supervisor classified the email",
    "billing": "💳 Billing agent checked the customer record and billing policy",
    "technical": "🛠️ Technical agent searched the help centre",
    "sales": "📈 Sales agent checked pricing",
    "escalate": "🙋 Routed to a human (outside the agents' scope)",
    "writer": "✍️ Writer drafted a reply",
    "reviewer": "🔍 QA agent reviewed the draft",
    "send": "📤 Reply sent",
    "discard": "🗑️ Draft discarded",
}


def describe(node: str, update: dict) -> str:
    if node == "supervisor":
        return f"Category **{update.get('category')}**, urgency **{update.get('urgency')}**: {update.get('summary', '')}"
    if node in ("billing", "technical", "sales"):
        return f"Sources: {', '.join(update.get('sources', [])) or 'none'}\n\n{update.get('notes', '')}"
    if node == "writer":
        return update.get("draft", "")
    if node == "reviewer":
        problems = update.get("review_feedback") or []
        return "Problems found, sent back to the writer:\n- " + "\n- ".join(problems) if update.get("rewrites") else (
            "Approved for human review." + (" Notes: " + "; ".join(problems) if problems else ""))
    return ""


def app():
    if "support_app" not in st.session_state:
        model = OpenAICompatibleLLM(llm.require_key(), llm.SMART, llm.GROQ_BASE_URL)
        st.session_state.support_outbox = []
        st.session_state.support_app = build_graph(model, outbox=st.session_state.support_outbox, checkpointer=InMemorySaver())
    return st.session_state.support_app


def run(payload) -> None:
    config = {"configurable": {"thread_id": st.session_state.support_thread}}
    log = st.session_state.support_log
    with st.status("Agents working…", expanded=True) as status:
        for chunk in app().stream(payload, config, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    continue
                if isinstance(update, dict):
                    log.append((node, describe(node, update)))
                    st.markdown(f"**{STEP.get(node, node)}**")
        status.update(label="Agents finished", state="complete", expanded=False)


ui.header(
    "LangGraph Support Agents",
    "A team of AI agents answers customer support email. A supervisor routes each email to a billing, technical or "
    "sales specialist, a writer drafts the reply, a QA agent checks it against the facts, and **nothing is sent "
    "until a human approves it**.",
    "langgraph-support-agents",
    flow=["Supervisor routes", "Specialist gathers facts", "Writer drafts", "QA agent reviews", "Human approves → send"],
)

pick = st.pills("Sample emails", list(INBOX), default=list(INBOX)[1])
raw = st.text_area("Incoming email (From / Subject / body)", value=INBOX.get(pick, ""), height=170, key=f"email_{pick}")

if st.button("Run the agents", type="primary"):
    try:
        app()
        st.session_state.support_thread = uuid.uuid4().hex
        st.session_state.support_log = []
        run({"raw_email": raw})
    except Exception as exc:
        llm.friendly_error(exc)

if st.session_state.get("support_thread"):
    config = {"configurable": {"thread_id": st.session_state.support_thread}}
    for node, text in st.session_state.support_log:
        with st.expander(STEP.get(node, node)):
            st.markdown(text or "—")
    state = app().get_state(config)
    pending = [i.value for t in state.tasks for i in t.interrupts]
    if pending:
        p = pending[0]
        st.subheader("⏸ Waiting for your approval")
        st.caption(f"To: {p['to']} · {p['subject']} · {p['category']}, {p['urgency']} urgency · sources: {', '.join(p['sources'])}")
        text = st.text_area("Draft reply (edit it if you like)", value=p["draft"], height=220)
        a, b, c = st.columns(3)
        try:
            if a.button("Approve & send", type="primary"):
                run(Command(resume={"action": "approve"} if text == p["draft"] else {"action": "edit", "text": text}))
                st.rerun()
            if c.button("Reject"):
                run(Command(resume={"action": "reject"}))
                st.rerun()
        except Exception as exc:
            llm.friendly_error(exc)
    else:
        outcome = state.values.get("outcome")
        if outcome == "sent":
            st.success("Sent after human approval. This is what went out:")
            st.code(st.session_state.support_outbox[-1]["body"], language=None)
        elif outcome:
            st.info(f"Outcome: {outcome}")
ui.footer()
