import altair as alt
import pandas as pd
import streamlit as st

from relay import core, style

sb = core.sandbox()
df = sb.frame()
style.title("Analytics", "How the agent team performed over the last two weeks.")

done = df[df["status"].isin(["Sent", "Rejected", "Resolved by staff"])]
drafted = df[df["category"].isin(["billing", "technical", "sales"]) & df["drafted_at"].notna()]
k = st.columns(5)
k[0].metric("Tickets", len(df), border=True)
k[1].metric("Drafted by AI", f"{len(drafted) / max(1, len(df[df['category'] != '–'])):.0%}", border=True)
k[2].metric("QA catches", int((drafted["rewrites"] > 0).sum()), help="Drafts the reviewer sent back to the writer before a human saw them", border=True)
k[3].metric("Sent with no edits", f"{(done['decision'] == 'Approved as written').mean():.0%}", border=True)
k[4].metric("Median time to resolve", f"{df['resolve_mins'].median():.0f} min", border=True)

PALETTE = alt.Scale(domain=["billing", "technical", "sales", "other"], range=["#7b5cf0", "#1aa0b5", "#f08a3c", "#a3a8bd"])
a, b = st.columns(2, gap="large")
with a:
    st.subheader("What customers write about")
    c = df[df["category"] != "–"].groupby("category").size().reset_index(name="tickets")
    st.altair_chart(alt.Chart(c).mark_arc(innerRadius=60).encode(
        theta="tickets:Q", color=alt.Color("category:N", scale=PALETTE, title=None, legend=alt.Legend(orient="right")),
        tooltip=["category", "tickets"]).properties(height=260), width="stretch")
with b:
    st.subheader("What happened to each draft")
    d = done.groupby("decision").size().reset_index(name="tickets")
    st.altair_chart(alt.Chart(d).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("decision:N", title=None, sort="-x", axis=alt.Axis(labelLimit=200)), x=alt.X("tickets:Q", title=None),
        color=alt.Color("decision:N", legend=None, scale=alt.Scale(
            domain=["Approved as written", "Edited, then sent", "Answered by staff", "Rejected"],
            range=["#1d9a5c", "#3b4fd8", "#7aa6d8", "#c9cdd9"])), tooltip=["decision", "tickets"]).properties(height=260), width="stretch")

c1, c2 = st.columns(2, gap="large")
with c1:
    st.subheader("Time to resolve")
    r = df.dropna(subset=["resolve_mins"]).assign(bucket=lambda x: pd.cut(x["resolve_mins"], [0, 15, 30, 60, 120, 10_000],
                                                                           labels=["< 15 min", "15–30 min", "30–60 min", "1–2 h", "> 2 h"]))
    r = r.groupby("bucket", observed=False).size().reset_index(name="tickets")
    st.altair_chart(alt.Chart(r).mark_bar(color="#3b4fd8", cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("bucket:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)), y=alt.Y("tickets:Q", title=None),
        tooltip=["bucket", "tickets"]).properties(height=240), width="stretch")
with c2:
    st.subheader("Approvals by teammate")
    p = done[done["assignee"].notna() & (done["assignee"] != "AI agents")].groupby(["assignee", "decision"]).size().reset_index(name="tickets")
    st.altair_chart(alt.Chart(p).mark_bar().encode(
        x=alt.X("assignee:N", title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y("tickets:Q", title=None, stack=True),
        color=alt.Color("decision:N", title=None, legend=alt.Legend(orient="bottom"), scale=alt.Scale(
            domain=["Approved as written", "Edited, then sent", "Answered by staff", "Rejected"],
            range=["#1d9a5c", "#3b4fd8", "#7aa6d8", "#c9cdd9"])), tooltip=["assignee", "decision", "tickets"]).properties(height=240),
        width="stretch")

st.subheader("Mistakes the QA reviewer caught")
caught = []
for t in sb.tickets.values():
    for s in t["trace"]:
        if s.get("rewrite"):
            caught.append({"Ticket": t["id"], "Subject": t["subject"], "What the reviewer flagged": s["text"].split("\n- ", 1)[-1]})
st.dataframe(pd.DataFrame(caught), hide_index=True, width="stretch")
