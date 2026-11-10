import datetime as dt
import html

import altair as alt
import pandas as pd
import streamlit as st

from glow import core, style

sb = core.sandbox()
now = core.local_now()
today = now.date()
greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"
style.title(f"{greeting}, Glow team", f"{now:%A %d %B} · here's what your WhatsApp assistant has been doing")

df = sb.bookings()
convos = sb.conversations()
waiting = [c for c in convos if c["mode"] == "human"]
week_ago, two_weeks = now - dt.timedelta(days=7), now - dt.timedelta(days=14)
ai = df[df["source"] == "AI agent"]
active = df[df["state"] != "Cancelled"]
chats_week = sum(1 for c in convos if c["last_at"] >= week_ago)
chats_prev = sum(1 for c in convos if two_weeks <= c["last_at"] < week_ago)
replies = sb.reply_seconds()
ai_share = len(ai[ai["state"] != "Cancelled"]) / max(1, len(active))

if waiting:
    w = waiting[0]
    with st.container(border=True):
        a, b = st.columns([5, 1], vertical_alignment="center")
        a.markdown(f"**{len(waiting)} chat{'s' if len(waiting) > 1 else ''} need{'s' if len(waiting) == 1 else ''} a person.** "
                   f"{html.escape(w['name'])}: “{html.escape(w['last_text'][:90])}” · {style.ago(w['last_at'])}", unsafe_allow_html=True)
        if b.button("Open inbox", type="primary", width="stretch"):
            st.session_state.inbox_sel = w["phone"]
            st.switch_page("views/inbox.py")

k = st.columns(5)
k[0].metric("Chats this week", chats_week, f"{chats_week - chats_prev:+d} vs last week", border=True)
k[1].metric("AI bookings", len(ai[ai["state"] != "Cancelled"]), f"{ai_share:.0%} of all bookings", delta_color="off", border=True)
k[2].metric("AI revenue", f"Rs {ai[ai['state'] != 'Cancelled']['price'].sum() / 1000:,.0f}k", "2 weeks + upcoming", delta_color="off", border=True)
k[3].metric("Avg reply time", f"{sum(replies) / max(1, len(replies)):.0f} sec", "day and night", delta_color="off", border=True)
k[4].metric("Waiting for staff", len(waiting), "waiting now" if waiting else "nothing waiting", delta_color="inverse" if waiting else "off", border=True)

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Bookings per day")
    days = pd.date_range(today - dt.timedelta(days=13), today + dt.timedelta(days=6), freq="D")
    daily = active.assign(day=active["start"].dt.normalize()).groupby(["day", "source"]).size().reset_index(name="bookings")
    daily = daily[daily["day"].isin(days)]
    chart = alt.Chart(daily).mark_bar(size=14, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b", labelAngle=0, tickCount=10)),
        y=alt.Y("bookings:Q", title=None, stack=True),
        color=alt.Color("source:N", title=None, scale=alt.Scale(domain=["AI agent", "Front desk", "Phone call"],
                                                                range=["#8b3a62", "#7d8cc4", "#e0a84a"]),
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("day:T", format="%A %d %b"), "source", "bookings"],
    )
    rule = alt.Chart(pd.DataFrame({"day": [pd.Timestamp(today)]})).mark_rule(strokeDash=[4, 3], color="#999").encode(x="day:T")
    st.altair_chart((chart + rule).properties(height=260), width="stretch")

    st.subheader("Today's appointments")
    todays = df[(df["start"].dt.date == today) & (df["state"] != "Cancelled")]
    if todays.empty:
        st.caption("No appointments today (the salon is closed on Sundays).")
    else:
        rows = "".join(
            f"<div><time>{r.start:%-I:%M %p}</time><span><b>{html.escape(r.name)}</b> · {r.label} "
            f"{style.pill(r.state)} {style.pill(r.source)}</span></div>" for r in todays.itertuples())
        st.markdown(f'<div class="feed">{rows}</div>', unsafe_allow_html=True)

with right:
    st.subheader("Live activity")
    icons = {"booking": "📅", "slack": "🙋", "whatsapp": "💬", "staff": "🧑‍💼"}
    rows = "".join(f"<div><time>{style.stamp(e['at'])}</time><span>{icons.get(e['kind'], '•')} {html.escape(e['text'].replace(':raising_hand: ', ''))}</span></div>"
                   for e in sb.events(12))
    st.markdown(f'<div class="feed">{rows}</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("**Try it yourself**  \nMessage the salon from a customer's phone. The AI checks the real "
                    "appointment book, books you in, and the booking shows up here and in Appointments.")
        if st.button("Open the customer's phone", icon=":material/smartphone:", width="stretch"):
            st.switch_page("views/phone.py")
