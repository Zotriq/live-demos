import hashlib
import hmac
import html
import json
import tempfile
import time
import uuid
from pathlib import Path

import streamlit as st
from fastapi.testclient import TestClient

from lib import llm, ui

repo = ui.project_path("whatsapp-ai-agent")
from wa_agent.agent import OpenAIChatModel  # noqa: E402
from wa_agent.app import create_app  # noqa: E402
from wa_agent.store import Store  # noqa: E402

SECRET = "demo-app-secret"
PHONE, NAME = "923001234567", "Demo Customer"
EXAMPLES = [
    "Hi! What services do you have and how much is a facial?",
    "Can I book a haircut tomorrow at 4pm? My name is Ali",
    "kal shaam 5 baje manicure ho sakta hai?",
    "What bookings do I have?",
    "This is the worst service ever, I want to speak to the manager",
]
CSS = """<style>
.wa { background:#efeae2; border-radius:10px; padding:14px; min-height:120px; }
.dark .wa, [data-theme="dark"] .wa { background:#0b141a; }
.wa-row { display:flex; margin:6px 0; } .wa-row.me { justify-content:flex-end; }
.wa-b { max-width:78%; padding:7px 10px 5px; border-radius:8px; font-size:15px; line-height:1.35; color:#111b21;
  box-shadow:0 1px .5px rgba(0,0,0,.13); white-space:pre-wrap; }
.wa-row.me .wa-b { background:#d9fdd3; } .wa-row.bot .wa-b { background:#fff; }
.wa-t { font-size:11px; color:#667781; text-align:right; margin-top:2px; }
.wa-head { display:flex; gap:10px; align-items:center; background:#075e54; color:#fff; padding:10px 14px; border-radius:10px 10px 0 0; margin-bottom:-6px; }
.wa-head b { font-size:15px; } .wa-head span { font-size:12px; opacity:.85; }
</style>"""


def session():
    if "wa" not in st.session_state:
        store = Store(Path(tempfile.mkdtemp()) / "wa.db")
        sent, staff = [], []

        class Sender:
            def send_text(self, to: str, body: str) -> None:
                sent.append({"to": to, "body": body, "at": time.strftime("%H:%M")})

        model = OpenAIChatModel(llm.require_key(), llm.SMART, llm.GROQ_BASE_URL)
        app = create_app(store, model, Sender(), app_secret=SECRET, verify_token="v", admin_token="admin",
                         notify_staff=staff.append)
        st.session_state.wa = {"client": TestClient(app), "store": store, "sent": sent, "staff": staff,
                               "chat": [], "webhooks": []}
    return st.session_state.wa


def send(text: str) -> None:
    s = session()
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "PNID"},
        "contacts": [{"wa_id": PHONE, "profile": {"name": NAME}}],
        "messages": [{"from": PHONE, "id": f"wamid.{uuid.uuid4().hex}", "timestamp": str(int(time.time())),
                      "type": "text", "text": {"body": text}}]}}]}]}
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    s["chat"].append({"me": True, "body": text, "at": time.strftime("%H:%M")})
    before = len(s["sent"])
    started = time.time()
    resp = s["client"].post("/webhook", content=body, headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"})
    s["webhooks"].append(f"POST /webhook · signature ✓ · {resp.status_code} {resp.json()} · {time.time() - started:.1f}s")
    for m in s["sent"][before:]:
        s["chat"].append({"me": False, "body": m["body"], "at": m["at"]})


ui.header(
    "WhatsApp AI Agent",
    "Runs a salon's WhatsApp number: answers questions in English or Urdu, checks the real appointment book, "
    "books and cancels with tool calling, and hands angry or complicated chats to a human.",
    "whatsapp-ai-agent",
    flow=["Customer message", "Signed webhook → signature check + dedupe", "AI with 6 tools", "Booking in the schedule", "Reply, or hand off to staff"],
    note="Every message you type is sent to the project's real webhook server exactly as Meta would send it "
         "(signed JSON payload); the reply that would go back to WhatsApp is shown in the chat.",
)

st.link_button("Open the full app: Glow Desk (inbox, calendar, customers, analytics) ↗", "https://zotriq-glow-desk.streamlit.app/", type="primary")
s = session()
chat_col, side_col = st.columns([3, 2])
with chat_col:
    st.markdown(CSS, unsafe_allow_html=True)
    rows = "".join(
        f'<div class="wa-row {"me" if m["me"] else "bot"}"><div class="wa-b">{html.escape(m["body"])}'
        f'<div class="wa-t">{m["at"]}{" ✓✓" if m["me"] else ""}</div></div></div>' for m in s["chat"]
    ) or '<div class="wa-t" style="text-align:center">Send a message to start the chat</div>'
    st.markdown('<div class="wa-head"><b>Glow Salon &amp; Spa</b><span>AI assistant · usually replies instantly</span></div>'
                f'<div class="wa">{rows}</div>', unsafe_allow_html=True)
    pick = st.pills("Try", EXAMPLES, key=f"wa_pick_{len(s['chat'])}")
    typed = st.chat_input("Type a message")
    text = typed or pick
    if text:
        try:
            with st.spinner("Agent is replying…"):
                send(text)
        except Exception as exc:
            llm.friendly_error(exc)
        st.rerun()

with side_col:
    st.markdown("**Behind the scenes**")
    convo = s["store"].conversation(PHONE, NAME)
    if convo["mode"] == "human":
        st.warning("Chat handed to a human. The bot now stays quiet until staff release it.")
    tools = []
    for m in s["store"].history(PHONE, limit=200):
        for call in m.get("tool_calls") or []:
            tools.append(f"`{call['function']['name']}({call['function'].get('arguments', '')})`")
    with st.expander(f"Tool calls ({len(tools)})", expanded=True):
        st.markdown("\n".join(f"- {t}" for t in tools) or "None yet")
    bookings = s["store"].conn.execute("SELECT code, name, service, starts_at, status FROM bookings ORDER BY starts_at").fetchall()
    with st.expander(f"Appointment book ({len(bookings)})", expanded=bool(bookings)):
        st.table([dict(b) for b in bookings]) if bookings else st.caption("No bookings yet")
    with st.expander(f"Staff alerts in Slack ({len(s['staff'])})", expanded=bool(s["staff"])):
        st.markdown("\n".join(f"- {a}" for a in s["staff"]) or "None")
    with st.expander("Webhook log"):
        st.markdown("\n".join(f"- {w}" for w in s["webhooks"]) or "No requests yet")
    if s["chat"] and st.button("Start a new chat"):
        del st.session_state["wa"]
        st.rerun()
ui.footer()
