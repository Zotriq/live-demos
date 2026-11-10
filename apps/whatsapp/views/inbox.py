import html

import pandas as pd
import streamlit as st

from glow import core, style

sb = core.sandbox()
style.title("Inbox", "Every WhatsApp conversation, with what the AI did in each one. Chats the AI hands over wait here for a person.")

convos = sb.conversations()
f1, f2 = st.columns([2, 3])
view = f1.segmented_control("Show", ["All", "Needs a person", "AI handling"], default="All", label_visibility="collapsed")
query = f2.text_input("Search", placeholder="Search by name, number or message", label_visibility="collapsed")
shown = [c for c in convos
         if (view in (None, "All") or (view == "Needs a person") == (c["mode"] == "human"))
         and (not query or query.lower() in (c["name"] + c["phone"] + c["last_text"]).lower())]

if not shown:
    st.info("No conversations match.")
    st.stop()

phones = [c["phone"] for c in shown]
sel = st.session_state.get("inbox_sel")
if sel not in phones:
    sel = phones[0]

left, mid, right = st.columns([1.15, 1.9, 1.0], gap="medium")
with left:
    table = pd.DataFrame({
        " ": ["🔴" if c["mode"] == "human" else "🟢" for c in shown],
        "Customer": [c["name"] for c in shown],
        "Last message": [c["last_text"].replace("\n", " ")[:80] for c in shown],
        "When": [style.ago(c["last_at"]) for c in shown],
    })
    event = st.dataframe(table, hide_index=True, height=640, on_select="rerun", selection_mode="single-row",
                         key=f"inbox_table_{abs(hash(tuple(phones)))}", width="stretch",
                         column_order=[" ", "Customer", "When"],
                         column_config={" ": st.column_config.TextColumn(width=28),
                                        "Customer": st.column_config.TextColumn(width="medium"),
                                        "When": st.column_config.TextColumn(width="small")})
    st.caption("🔴 needs a person · 🟢 AI is handling it")
    if event.selection.rows:
        sel = phones[event.selection.rows[0]]
    st.session_state.inbox_sel = sel

convo = next(c for c in shown if c["phone"] == sel)
msgs = sb.messages(sel)
with mid:
    status = "Waiting for a person · the AI is paused" if convo["mode"] == "human" else "AI assistant is replying"
    st.markdown(
        f'<div class="wa-head"><div class="av">{style.initials(convo["name"])}</div><div><b>{html.escape(convo["name"])}</b>'
        f'<span>+{sel} · {status}</span></div></div>'
        f'<div class="wa joined" style="height:470px;overflow-y:auto;display:flex;flex-direction:column-reverse">'
        f'<div>{style.chat(msgs[-60:])}</div></div>', unsafe_allow_html=True)

    if convo["mode"] == "human":
        quick = st.pills("Quick replies", [
            "So sorry about this. We'd like to offer you 20% off your next visit.",
            "Thanks for your patience! I'm checking this now and will get back to you in a few minutes.",
            "I've booked that for you. You'll get a confirmation here shortly.",
        ], key=f"quick_{sel}_{len(msgs)}")
        with st.form(f"reply_{sel}", clear_on_submit=True, border=False):
            c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
            text = c1.text_input("Reply as staff", value=quick or "", placeholder="Type a reply as Sadia (front desk)")
            send = c2.form_submit_button("Send", type="primary", width="stretch")
        if send and text.strip():
            sb.staff_reply(sel, text.strip())
            st.rerun()
        if st.button("Hand back to the AI", icon=":material/smart_toy:", help="Calls the agent's admin API: POST /admin/release/{phone}"):
            sb.release(sel)
            st.toast("The AI is handling this chat again")
            st.rerun()
    else:
        c1, c2 = st.columns([3, 2], vertical_alignment="center")
        c1.caption("The AI is answering this customer. Take over to reply yourself; the AI stays quiet until you hand it back.")
        if c2.button("Take over", icon=":material/front_hand:", width="stretch"):
            sb.take_over(sel)
            st.rerun()

with right:
    df = sb.bookings()
    mine = df[df["phone"] == sel]
    done = mine[mine["state"] == "Completed"]
    up = mine[mine["state"].isin(["Upcoming", "In progress"])]
    with st.container(border=True):
        st.markdown(f"**{html.escape(convo['name'])}**")
        st.markdown(
            f'<div class="kv"><b>WhatsApp</b> +{sel}<br><b>Language</b> {convo["language"]}<br>'
            f'<b>Visits</b> {len(done)}<br><b>Spent</b> Rs {done["price"].sum():,.0f}<br>'
            f'<b>Status</b> {style.pill(convo["mode"])}</div>', unsafe_allow_html=True)
    st.markdown("**Upcoming**")
    if up.empty:
        st.caption("No upcoming appointments")
    for r in up.itertuples():
        st.markdown(f"{r.start:%a %d %b · %-I:%M %p}  \n{r.label} · `{r.code}` {style.pill(r.source)}", unsafe_allow_html=True)
    tools = [c for m in msgs for c in m["tool_calls"]]
    st.markdown(f"**AI actions in this chat** ({len(tools)})")
    st.markdown("\n".join(f"- {style.tool_text(c)[2:]}" for c in tools[-8:]) or "None yet")
