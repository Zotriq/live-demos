import streamlit as st

from relay import core, style
from support_agents.graph import MAX_REWRITES

sb = core.sandbox()
style.title("Agents & rules", "How the agent team is wired. This is the LangGraph graph the app runs for every ticket.")

st.graphviz_chart("""
digraph {
  rankdir=LR; bgcolor="transparent"; node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=11 color="#c9cff0" fillcolor="#ffffff"];
  edge [color="#8a93c4" fontname="Helvetica" fontsize=9];
  email [label="New email" fillcolor="#eef0fd"];
  supervisor [label="Supervisor\\nclassify + urgency" fillcolor="#e8ecff"];
  billing [label="Billing agent\\ncustomer record + policy"]; technical [label="Technical agent\\nhelp-centre search"];
  sales [label="Sales agent\\npricing + account"]; escalate [label="Escalate\\nto a person" fillcolor="#fde7ea"];
  writer [label="Writer\\ndraft reply"]; reviewer [label="QA reviewer\\nfact check"];
  human [label="Human approval\\n(graph pauses)" fillcolor="#fff1d6"]; send [label="Send" fillcolor="#e3f5ec"]; discard [label="Discard"];
  email -> supervisor; supervisor -> billing; supervisor -> technical; supervisor -> sales; supervisor -> escalate;
  billing -> writer; technical -> writer; sales -> writer; writer -> reviewer;
  reviewer -> writer [label="problems found" style=dashed]; reviewer -> human [label="approved"];
  human -> send [label="approve / edit"]; human -> discard [label="reject"];
}
""", width="stretch")

a, b = st.columns(2, gap="large")
with a:
    st.subheader("Rules")
    st.markdown(f"""
- **Every reply needs a person.** The graph stops at *Human approval* (a LangGraph interrupt) and only continues when someone approves, edits or rejects.
- **Facts only.** Specialists may use only the customer record and the knowledge base; the writer may use only the specialist's notes.
- **QA before humans.** The reviewer rejects drafts that promise things the notes don't support, up to **{MAX_REWRITES} rewrites**.
- **Know the limits.** Anything outside billing, technical or sales (legal, press, partnerships) is escalated with no AI draft.
- **Refund limit.** Agents follow the billing policy: duplicate charges are refunded; refunds over $1,000 need a manager.
""")
with b:
    st.subheader("The team")
    for node in ("supervisor", "billing", "technical", "sales", "writer", "reviewer"):
        who, what = core.STEP[node]
        st.markdown(f"**{who}** · {what}")
    st.caption(f"Each agent is a LangGraph node. Model: {core.llm.SMART} on Groq. "
               f"Every ticket is its own thread with saved state, so an approval can wait hours or days.")

st.divider()
if st.button("Reset demo data", icon=":material/restart_alt:"):
    core.reset()
    st.rerun()
