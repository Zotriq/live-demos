import pandas as pd
import streamlit as st

from lib import llm
from ops import core, style

w = core.ws()
style.title("Team & tasks", "Who does what: every recurring job is owned by a contractor, an AI agent, an automation, the operator, or the founder.")

df = pd.DataFrame(w.tasks)
k = st.columns(5)
for col, kind in zip(k, core.OWNER_TYPES):
    n = int((df["type"] == kind).sum())
    col.metric(kind if kind != "AI agent" else "AI agents", n, f"{n / len(df):.0%} of the work", delta_color="off", border=True)

f1, f2 = st.columns(2)
types = f1.multiselect("Owner type", core.OWNER_TYPES, placeholder="All owner types")
status = f2.multiselect("Status", ["Not started", "In progress", "Done"], default=["Not started", "In progress"])
view = df[(df["type"].isin(types) if types else True) & (df["status"].isin(status) if status else True)].sort_values("due")
edited = st.data_editor(
    view[["task", "stream", "owner", "type", "status", "due"]], hide_index=True, width="stretch", key="tasks",
    column_config={"task": st.column_config.TextColumn("Task", width="large"), "stream": "Stream", "owner": "Owner",
                   "type": st.column_config.SelectboxColumn("Owner type", options=core.OWNER_TYPES),
                   "status": st.column_config.SelectboxColumn("Status", options=["Not started", "In progress", "Done"]),
                   "due": st.column_config.DateColumn("Due", format="ddd MMM D")},
    disabled=["stream", "owner", "due"])
for idx, row in edited.iterrows():
    w.tasks[idx]["status"], w.tasks[idx]["type"], w.tasks[idx]["task"] = row["status"], row["type"], row["task"]

st.subheader("Turn a task into an SOP")
st.caption("Pick any recurring task: the AI writes a one-page standard operating procedure a contractor can follow, "
           "and marks the steps an AI agent or automation could take over.")
a, b = st.columns([3, 1], vertical_alignment="bottom")
task = a.selectbox("Task", [x["task"] for x in w.tasks])
if b.button("Write SOP", type="primary", width="stretch") and not core.need_key():
    item = next(x for x in w.tasks if x["task"] == task)
    try:
        with st.spinner("Writing the SOP…"):
            sop = core.ask_text(
                "You write short SOPs for a small AI agency. Format in markdown: Purpose (1 line), Owner, When, Tools, "
                "Steps (numbered, max 8, each one line; tag a step [AI] or [Automation] when it could be handed to an AI agent "
                "or automation), Done when (1 line), Watch out for (2 bullets).",
                [{"role": "user", "content": f"Task: {item['task']}. Stream: {item['stream']}. Current owner: {item['owner']} ({item['type']}). "
                                             "Tools available: GoHighLevel CRM, ChatGPT/Claude, Canva, Google Drive."}])
        st.session_state.sop = (task, sop)
    except Exception as exc:  # noqa: BLE001
        llm.friendly_error(exc)
if st.session_state.get("sop") and st.session_state.sop[0] == task:
    with st.container(border=True):
        st.markdown(st.session_state.sop[1])
