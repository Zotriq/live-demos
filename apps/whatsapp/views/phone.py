import html
import json

import streamlit as st

from glow import core, style
from lib import llm

sb = core.sandbox()
style.title("Customer's phone", "Message the salon as a customer would. Each message goes to the agent's real webhook, "
            "signed exactly the way Meta's WhatsApp Cloud API signs it.")

NEW = ("923007654321", "Ali Raza")
people = {NEW[0]: NEW[1]} | {c["phone"]: c["name"] for c in sb.conversations()}
EXAMPLES = [
    "Hi! What services do you have and how much is a facial?",
    "Can I book a haircut tomorrow at 4pm? My name is Ali",
    "kal shaam 5 baje manicure ho sakta hai?",
    "What bookings do I have?",
    "Please cancel my booking",
    "This is the worst service ever, I want to speak to the manager",
]

EMPTY = ('<div class="wa-day"><span style="background:#fdf4c5">🔒 Messages to this business are handled by an AI assistant '
         'and its team.</span></div>')

left, right = st.columns([1, 1.15], gap="large")
with left:
    phone = st.selectbox("Messaging as", list(people), format_func=lambda p: f"{people[p]} · +{p}" + ("  (new customer)" if p == NEW[0] else ""))
    name = people[phone]
    msgs = sb.messages(phone)
    mode = sb.store.conversation(phone, name)["mode"] if msgs else "bot"
    st.markdown(
        '<div class="phone"><div class="bar"><span>9:41</span><span>●●● 5G ▮</span></div>'
        '<div class="wa-head"><div class="av" style="background:#f5e6ee;color:#8b3a62">G</div><div><b>Glow Salon &amp; Spa</b>'
        f'<span>{"a team member will reply" if mode == "human" else "Business account · replies instantly"}</span></div></div>'
        f'<div class="wa" style="flex-direction:column-reverse"><div>{style.chat(msgs[-40:], customer_view=True) or EMPTY}</div>'
        f'<div class="spacer"></div></div></div>', unsafe_allow_html=True)
    if not msgs:
        st.caption("New chat. Pick an example below or type your own message, in English or Urdu.")
    pick = st.pills("Try", EXAMPLES, key=f"pick_{phone}_{len(msgs)}", label_visibility="collapsed")
    typed = st.chat_input("Message Glow Salon & Spa")
    text = typed or pick
    if text:
        if not llm.groq_key():
            st.error("This deployment has no GROQ_API_KEY secret, so the AI can't reply.")
            st.stop()
        try:
            with st.spinner("Glow Salon is typing…"):
                sb.customer_says(phone, name, text)
        except Exception as exc:  # noqa: BLE001
            llm.friendly_error(exc)
            st.stop()
        st.rerun()

with right:
    run = sb.last_run if sb.last_run and sb.last_run["phone"] == phone else None
    st.subheader("Behind the scenes")
    if not run:
        st.caption("Send a message and this panel shows each step: the webhook, every tool the AI called with its "
                   "real inputs and outputs, and the reply that went back to WhatsApp.")
    else:
        steps = [("Webhook received", f"POST /webhook → {run['status']} · HMAC-SHA256 signature verified · "
                                      f"message id checked for duplicates · answered in {run['ms'] / 1000:.1f}s")]
        results = {}
        for m in run["messages"]:
            if m["role"] == "tool":
                msg = json.loads(m["content"])
                results[msg["tool_call_id"]] = json.loads(msg["content"])
        for m in run["messages"]:
            msg = json.loads(m["content"])
            for call in msg.get("tool_calls") or []:
                out = results.get(call["id"], {})
                steps.append((f"Tool: {call['function']['name']}",
                              f"in: {call['function'].get('arguments') or '{}'}\nout: {json.dumps(out, ensure_ascii=False)[:400]}"))
            if msg["role"] == "assistant" and msg.get("content") and not msg.get("tool_calls"):
                steps.append(("Reply sent to WhatsApp", msg["content"][:200]))
        for a in run["alerts"]:
            steps.append(("Staff alert (Slack)", a.replace(":raising_hand: ", "")))
        st.markdown("".join(f'<div class="step"><b>{t}</b><br><code>{html.escape(d)}</code></div>'
                            for t, d in steps), unsafe_allow_html=True)
    st.divider()
    st.markdown("**See the result in the business app**")
    c1, c2, c3 = st.columns(3)
    if c1.button("Inbox", icon=":material/forum:", width="stretch"):
        st.session_state.inbox_sel = phone
        st.switch_page("views/inbox.py")
    if c2.button("Appointments", icon=":material/calendar_month:", width="stretch"):
        st.switch_page("views/appointments.py")
    if c3.button("Overview", icon=":material/space_dashboard:", width="stretch"):
        st.switch_page("views/overview.py")
    with st.expander("What the AI can do"):
        st.markdown("- Answer questions about services, prices, hours and policies\n"
                    "- Check free times in the real appointment book (2 chairs, 30-minute slots)\n"
                    "- Book, list and cancel appointments; customers only ever see their own\n"
                    "- Reply in English, Urdu or Roman Urdu\n"
                    "- Hand complaints and special requests to a person, and alert staff in Slack")
