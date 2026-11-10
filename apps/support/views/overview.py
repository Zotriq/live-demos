import datetime as dt
import altair as alt
import pandas as pd
import streamlit as st

from relay import core, style

sb = core.sandbox()
df = sb.frame()
t_now = core.now()
style.title("Support overview", f"Lumen Analytics · {t_now:%A %d %B} · AI agents draft every reply, a person approves it")

week = df[df["received"] >= t_now - dt.timedelta(days=7)]
prev = df[(df["received"] < t_now - dt.timedelta(days=7)) & (df["received"] >= t_now - dt.timedelta(days=14))]
handled = df[df["status"].isin(["Sent", "Rejected"])]
first_time = (handled["decision"] == "Approved as written").mean() if len(handled) else 0
open_n = int(df["status"].isin(["New", "Needs approval", "Escalated"]).sum())

k = st.columns(5)
k[0].metric("Tickets this week", len(week), f"{len(week) - len(prev):+d} vs last week", border=True)
k[1].metric("Open now", open_n, f"{int((df['status'] == 'Needs approval').sum())} to approve", delta_color="off", border=True)
k[2].metric("Draft ready in", f"{df['draft_secs'].median():.0f} sec", "median", delta_color="off", border=True)
k[3].metric("Approved as written", f"{first_time:.0%}", "no edits needed", delta_color="off", border=True)
k[4].metric("Resolved in", f"{df['resolve_mins'].median():.0f} min", "incl. human review", delta_color="off", border=True)

need = df[df["status"].isin(["Needs approval", "Escalated", "New"])].sort_values("received")
if not need.empty:
    st.subheader("Needs your attention")
    for r in need.itertuples():
        with st.container(border=True):
            a, b = st.columns([6, 1], vertical_alignment="center")
            a.markdown(f"{style.status(r.status)} {style.cat(r.category)} {style.urg(r.urgency)} &nbsp; **{style.esc(r.subject)}**  \n"
                       f"<span style='opacity:.7;font-size:14px'>{style.esc(r.name)} · {style.esc(r.company)} · {style.ago(r.received)} · {r.id}</span>",
                       unsafe_allow_html=True)
            label = {"New": "Run agents", "Needs approval": "Review", "Escalated": "Answer"}[r.status]
            if b.button(label, key=f"open_{r.id}", type="primary" if r.status == "Needs approval" else "secondary", width="stretch"):
                core.open_ticket(r.id)

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Tickets per day")
    days = df.assign(day=pd.to_datetime(df["received"]).dt.normalize())
    days = days[days["category"] != "–"].groupby(["day", "category"]).size().reset_index(name="tickets")
    st.altair_chart(alt.Chart(days).mark_bar(size=16, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b", labelAngle=0)), y=alt.Y("tickets:Q", title=None),
        color=alt.Color("category:N", title=None, scale=alt.Scale(domain=["billing", "technical", "sales", "other"],
                                                                  range=["#7b5cf0", "#1aa0b5", "#f08a3c", "#a3a8bd"]),
                        legend=alt.Legend(orient="top")), tooltip=["day:T", "category", "tickets"]).properties(height=270),
        width="stretch")
with right:
    st.subheader("Recent activity")
    events = []
    for t in sb.tickets.values():
        for s in t["trace"]:
            if s["node"] in ("send", "discard", "escalate"):
                who, _ = core.STEP[s["node"]]
                verb = {"send": f"Reply sent to {t['name']}", "discard": f"Draft rejected for {t['name']}",
                        "escalate": f"{t['name']}'s email escalated to a person"}[s["node"]]
                events.append((s["at"], verb, t["subject"]))
    rows = "".join(f"<div><time>{style.ago(at)}</time><span>{style.esc(v)}<br><span style='opacity:.6;font-size:12.5px'>"
                   f"{style.esc(subj)}</span></span></div>" for at, v, subj in sorted(events, reverse=True)[:9])
    st.markdown(f'<div class="feed">{rows}</div>', unsafe_allow_html=True)
