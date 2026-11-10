import datetime as dt
import json

import altair as alt
import pandas as pd
import streamlit as st

from glow import core, style

sb = core.sandbox()
style.title("Analytics", "How the WhatsApp assistant is performing over the last two weeks.")

now = core.local_now()
since = now - dt.timedelta(days=14)
rows = []
for r in sb.db.execute("SELECT m.phone, m.role, m.content, m.at, mm.kind FROM messages m LEFT JOIN msg_meta mm ON mm.msg_id = m.id"):
    msg = json.loads(r["content"])
    rows.append({"phone": r["phone"], "role": r["role"], "kind": r["kind"], "at": core.to_local(r["at"]),
                 "text": msg.get("content") or "", "tools": [c["function"]["name"] for c in msg.get("tool_calls") or []]})
msgs = pd.DataFrame(rows)
msgs = msgs[msgs["at"] >= since]
customer = msgs[msgs["role"] == "user"]
answers = msgs[(msgs["role"] == "assistant") & (msgs["text"] != "")]
tools = msgs.explode("tools").dropna(subset=["tools"])
df = sb.bookings()
ai = df[(df["source"] == "AI agent") & (df["state"] != "Cancelled")]


def after_hours(t: dt.datetime) -> bool:
    h = sb.salon._hours(t.date())
    return not h or not (h[0] <= t < h[1])


chatted = set(customer["phone"])
booked = set(ai["phone"])
k = st.columns(5)
k[0].metric("Customer messages", len(customer), border=True)
k[1].metric("Answered by the AI", f"{(answers['kind'].isna()).mean():.0%}", border=True)
k[2].metric("Chats that booked", f"{len(chatted & booked) / max(1, len(chatted)):.0%}", border=True)
k[3].metric("Arrived after hours", f"{customer['at'].map(after_hours).mean():.0%}", help="Salon closed: no one at the desk, the AI still replied", border=True)
k[4].metric("Handed to staff", int((tools["tools"] == "handoff_to_human").sum()), border=True)

c1, c2 = st.columns(2, gap="large")
with c1:
    st.subheader("Messages per day")
    per_day = msgs[msgs["role"].isin(["user", "assistant"]) & (msgs["text"] != "")].assign(
        day=lambda d: pd.to_datetime(d["at"]).dt.normalize(),
        who=lambda d: d.apply(lambda r: "Customers" if r["role"] == "user" else ("Staff" if r["kind"] == "staff" else "AI assistant"), axis=1))
    data = per_day.groupby(["day", "who"]).size().reset_index(name="messages")
    st.altair_chart(alt.Chart(data).mark_line(point=True, strokeWidth=2.5).encode(
        x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b")), y=alt.Y("messages:Q", title=None),
        color=alt.Color("who:N", title=None, scale=alt.Scale(domain=["Customers", "AI assistant", "Staff"], range=["#7d8cc4", "#8b3a62", "#e0a84a"]),
                        legend=alt.Legend(orient="top")), tooltip=["day:T", "who", "messages"]).properties(height=260), width="stretch")
with c2:
    st.subheader("When customers message")
    hours = customer.assign(hour=customer["at"].map(lambda t: t.hour), open=customer["at"].map(lambda t: "Salon closed" if after_hours(t) else "Salon open"))
    data = hours.groupby(["hour", "open"]).size().reset_index(name="messages")
    st.altair_chart(alt.Chart(data).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("hour:O", title="Hour of day"), y=alt.Y("messages:Q", title=None),
        color=alt.Color("open:N", title=None, scale=alt.Scale(domain=["Salon open", "Salon closed"], range=["#d9b3c6", "#8b3a62"]),
                        legend=alt.Legend(orient="top")), tooltip=["hour", "open", "messages"]).properties(height=260), width="stretch")

c3, c4, c5 = st.columns(3, gap="large")
with c3:
    st.subheader("Revenue by service")
    rev = df[df["state"] != "Cancelled"].groupby(["label", "source"])["price"].sum().reset_index()
    st.altair_chart(alt.Chart(rev).mark_bar().encode(
        y=alt.Y("label:N", title=None, sort="-x", axis=alt.Axis(labelOverlap=False, labelLimit=160)), x=alt.X("price:Q", title="Rs", stack=True),
        color=alt.Color("source:N", title=None, scale=alt.Scale(domain=["AI agent", "Front desk", "Phone call"], range=["#8b3a62", "#7d8cc4", "#e0a84a"]),
                        legend=alt.Legend(orient="bottom")), tooltip=["label", "source", alt.Tooltip("price:Q", format=",")]).properties(height=240),
        width="stretch")
with c4:
    st.subheader("Languages")
    langs = pd.Series([c["language"] for c in sb.conversations()]).value_counts().reset_index()
    langs.columns = ["language", "chats"]
    st.altair_chart(alt.Chart(langs).mark_arc(innerRadius=55).encode(
        theta="chats:Q", color=alt.Color("language:N", title=None, scale=alt.Scale(range=["#8b3a62", "#e0a84a", "#7d8cc4"]),
                                        legend=alt.Legend(orient="bottom")), tooltip=["language", "chats"]).properties(height=240),
        width="stretch")
with c5:
    st.subheader("What the AI did")
    labels = {"check_availability": "Checked availability", "book_appointment": "Booked", "list_services": "Answered prices/info",
              "cancel_booking": "Cancelled", "my_bookings": "Looked up bookings", "handoff_to_human": "Handed to staff"}
    acts = tools["tools"].map(labels).value_counts().reset_index()
    acts.columns = ["action", "times"]
    st.altair_chart(alt.Chart(acts).mark_bar(color="#8b3a62").encode(
        y=alt.Y("action:N", title=None, sort="-x", axis=alt.Axis(labelOverlap=False, labelLimit=170)), x=alt.X("times:Q", title=None), tooltip=["action", "times"]).properties(height=240),
        width="stretch")
