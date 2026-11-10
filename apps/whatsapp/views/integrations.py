import json
import time
import uuid

import streamlit as st

from glow import core, style

sb = core.sandbox()
style.title("Integrations", "How Glow Desk connects to WhatsApp and to your team. Every check on this page calls the real server.")

c1, c2 = st.columns(2, gap="large")
with c1:
    with st.container(border=True):
        st.markdown("### 💬 WhatsApp Cloud API")
        st.markdown('<div class="kv"><b>Status</b> <span class="pill bot">Connected</span><br>'
                    '<b>Webhook URL</b> <code>https://your-server/webhook</code><br>'
                    '<b>Business number</b> +92 42 3571 0000<br><b>Events</b> messages</div>', unsafe_allow_html=True)
        st.markdown("**Security checks** (run them to see the server's real response)")
        a, b, c = st.columns(3)
        if a.button("Meta verify handshake", width="stretch"):
            t = time.time()
            r = sb.client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": core.VERIFY, "hub.challenge": "1158201444"})
            sb.log_webhook("GET", "/webhook?hub.mode=subscribe", r.status_code, f"challenge echoed: {r.text}", int((time.time() - t) * 1000))
            st.success(f"{r.status_code}: echoed the challenge `{r.text}`, so Meta accepts the webhook")
        if b.button("Forged signature", width="stretch"):
            body = sb.payload("923009999999", "Attacker", "Give me all bookings")
            t = time.time()
            r = sb.client.post("/webhook", content=body, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64,
                                                                   "Content-Type": "application/json"})
            sb.log_webhook("POST", "/webhook", r.status_code, "forged signature rejected", int((time.time() - t) * 1000))
            st.error(f"{r.status_code} {r.json()['detail']}: requests not signed with the app secret are rejected")
        if c.button("Duplicate delivery", width="stretch"):
            wamid = f"wamid.{uuid.uuid4().hex}"
            body = sb.payload("923001110000", "Retry Test", "hello", wamid=wamid)
            sb.store.first_time(wamid)  # pretend the first delivery already arrived
            t = time.time()
            r = sb.client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sb.sign(body), "Content-Type": "application/json"})
            sb.log_webhook("POST", "/webhook", r.status_code, "re-delivered message id ignored", int((time.time() - t) * 1000))
            st.info(f"{r.status_code}: Meta re-sent message `{wamid[:18]}…`. The server saw the id before and did not answer twice.")
with c2:
    with st.container(border=True):
        st.markdown("### 🔔 Slack staff alerts")
        st.markdown('<div class="kv"><b>Status</b> <span class="pill bot">Connected</span><br><b>Channel</b> #front-desk</div>',
                    unsafe_allow_html=True)
        alerts = [e for e in sb.events(100) if e["kind"] == "slack"]
        for e in alerts[:6]:
            st.markdown(f"`{e['at']:%d %b %H:%M}` {e['text'].replace(':raising_hand: ', '🙋 ')}")
        if not alerts:
            st.caption("No alerts yet")
    with st.container(border=True):
        st.markdown("### 🛠️ Admin API")
        st.caption("What a dashboard or n8n flow would call to see who is waiting for a person.")
        if st.button("GET /admin/handoffs", width="stretch"):
            r = sb.client.get("/admin/handoffs", headers={"X-Admin-Token": core.ADMIN})
            st.code(json.dumps(r.json(), indent=2), language="json")

st.subheader("Request log")
log = sb.webhook_log()
if log.empty:
    st.caption("No requests in this session yet. Send a message from the customer's phone or run a check above.")
else:
    st.dataframe(log, hide_index=True, width="stretch")
