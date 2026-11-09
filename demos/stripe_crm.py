import datetime as dt
import hashlib
import hmac
import json
import tempfile
import time
import uuid
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
from fastapi.testclient import TestClient

from lib import ui

repo = ui.project_path("stripe-crm-automation")
from stripe_automation.app import Services, create_app, run_due_actions  # noqa: E402
from stripe_automation.integrations import TEMPLATES, HubSpot, Mailer, Slack  # noqa: E402
from stripe_automation.store import Store, utcnow  # noqa: E402

SECRET = "whsec_demo"
EVENTS = {
    "New customer pays at checkout": "checkout.session.completed",
    "Subscription renewal paid": "invoice.paid",
    "Card payment failed": "invoice.payment_failed",
    "Charge refunded": "charge.refunded",
    "Subscription cancelled": "customer.subscription.deleted",
}


def event_object(kind: str, name: str, email: str, cents: int) -> dict:
    if kind == "checkout.session.completed":
        return {"id": "cs_" + uuid.uuid4().hex[:14], "object": "checkout.session", "payment_status": "paid", "amount_total": cents,
                "currency": "usd", "customer_details": {"email": email, "name": name, "phone": "+1 555 0100"}}
    if kind == "invoice.paid":
        return {"id": "in_" + uuid.uuid4().hex[:14], "object": "invoice", "billing_reason": "subscription_cycle",
                "customer_email": email, "amount_paid": cents, "currency": "usd"}
    if kind == "invoice.payment_failed":
        return {"id": "in_" + uuid.uuid4().hex[:14], "object": "invoice", "customer_email": email, "amount_due": cents,
                "currency": "usd", "attempt_count": 1, "hosted_invoice_url": "https://invoice.stripe.com/i/demo"}
    if kind == "charge.refunded":
        return {"id": "ch_" + uuid.uuid4().hex[:14], "object": "charge", "amount_refunded": cents, "currency": "usd",
                "billing_details": {"email": email}}
    return {"id": "sub_" + uuid.uuid4().hex[:14], "object": "subscription", "customer": "cus_" + uuid.uuid4().hex[:10],
            "cancellation_details": {"reason": "cancellation_requested"}}


def env():
    if "stripe" not in st.session_state:
        calls, emails = [], []
        state = {"hubspot_down": False}

        def transport(request: httpx.Request) -> httpx.Response:
            host = request.url.host
            body = json.loads(request.content or b"{}")
            down = host == "api.hubapi.com" and state["hubspot_down"]
            calls.append({"time": time.strftime("%H:%M:%S"), "service": "HubSpot" if "hubapi" in host else "Slack",
                          "request": f"{request.method} {request.url.path}", "body": body, "status": 503 if down else 200})
            return httpx.Response(503 if down else 200, json={"status": "error" if down else "ok"})

        http = httpx.Client(transport=transport)

        class DemoMailer(Mailer):
            def send(self, to, template, **values):  # same templates, captured instead of sent over SMTP
                subject, body = TEMPLATES[template]
                emails.append({"to": to, "subject": subject.format(**values), "body": body.format(**values)})

        store = Store(Path(tempfile.mkdtemp()) / "outbox.db")
        services = Services(
            crm=HubSpot("demo-token", client=httpx.Client(transport=httpx.MockTransport(transport), base_url="https://api.hubapi.com")),
            chat=Slack("https://hooks.slack.com/services/T000/B000/demo", client=httpx.Client(transport=httpx.MockTransport(transport))),
            mail=DemoMailer("", 0, "", "", "billing@example.com"),
        )
        st.session_state.stripe = {"client": TestClient(create_app(store, services, webhook_secret=SECRET, admin_token="admin")),
                                   "store": store, "services": services, "calls": calls, "emails": emails, "state": state,
                                   "log": [], "last": None}
    return st.session_state.stripe


def deliver(s, body: bytes, forged: bool = False) -> None:
    ts = str(int(time.time()))
    sig = hmac.new(SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={'0' * 64 if forged else sig}"
    r = s["client"].post("/stripe/webhook", content=body, headers={"Stripe-Signature": header, "Content-Type": "application/json"})
    event = json.loads(body)
    s["log"].append({"time": time.strftime("%H:%M:%S"), "event": event["type"], "id": event["id"],
                     "signature": "forged" if forged else "valid", "response": f"{r.status_code} {r.json()}"})


ui.header(
    "Stripe → CRM Automation",
    "When a payment happens in Stripe, the customer is added to HubSpot, gets a welcome (or payment-failed) email, "
    "and the team is told in Slack. Webhooks are signature-checked, duplicates are ignored, and failed steps are "
    "retried with backoff instead of lost.",
    "stripe-crm-automation",
    flow=["Stripe webhook", "Verify signature", "Save to outbox (once per event)", "HubSpot · email · Slack", "Retry with backoff"],
    note="This page sends correctly signed Stripe webhooks to the project's real FastAPI server. HubSpot and Slack "
         "are replaced by a recorder that shows the exact API calls the code makes; nothing leaves the page.",
)
s = env()

left, right = st.columns([2, 3])
with left:
    label = st.selectbox("Stripe event", list(EVENTS))
    name = st.text_input("Customer name", "Ayesha Khan")
    email = st.text_input("Customer email", "ayesha@example.com")
    amount = st.number_input("Amount (USD)", 1.0, 100000.0, 49.0, step=1.0)
    s["state"]["hubspot_down"] = st.toggle("Simulate a HubSpot outage", value=s["state"]["hubspot_down"])
    kind = EVENTS[label]
    if st.button("Send webhook", type="primary"):
        event = {"id": "evt_" + uuid.uuid4().hex[:20], "object": "event", "type": kind, "created": int(time.time()),
                 "data": {"object": event_object(kind, name, email, int(amount * 100))}}
        s["last"] = json.dumps(event).encode()
        deliver(s, s["last"])
    b1, b2 = st.columns(2)
    if s["last"] and b1.button("Resend same event"):
        deliver(s, s["last"])
    if s["last"] and b2.button("Send with forged signature"):
        deliver(s, s["last"], forged=True)
    pending = s["store"].conn.execute("SELECT count(*) FROM actions WHERE status = 'pending'").fetchone()[0]
    if pending and st.button(f"Run the retry worker now ({pending} waiting)"):
        # Fast-forward the backoff clock so the demo doesn't have to wait 30s–8min
        s["store"].conn.execute("UPDATE actions SET next_attempt_at = ? WHERE status = 'pending'", (utcnow().isoformat(),))
        run_due_actions(s["store"], s["services"])

with right:
    st.markdown("**Webhooks received**")
    st.dataframe(pd.DataFrame(s["log"][::-1]), width="stretch", hide_index=True) if s["log"] else st.caption("Send one on the left")
    rows = s["store"].conn.execute(
        "SELECT a.id, e.type AS event, a.kind, a.status, a.attempts, a.last_error, a.next_attempt_at FROM actions a "
        "JOIN events e ON e.id = a.event_id ORDER BY a.id DESC").fetchall()
    st.markdown("**Outbox** (every action is saved before it runs, so nothing is lost)")
    st.dataframe(pd.DataFrame([dict(r) for r in rows]), width="stretch", hide_index=True) if rows else st.caption("Empty")
    t1, t2 = st.tabs([f"HubSpot & Slack API calls ({len(s['calls'])})", f"Emails ({len(s['emails'])})"])
    with t1:
        for c in s["calls"][::-1]:
            st.markdown(f"`{c['time']}` **{c['service']}** `{c['request']}` → **{c['status']}**")
            st.json(c["body"], expanded=False)
        if not s["calls"]:
            st.caption("None yet")
    with t2:
        for m in s["emails"][::-1]:
            st.markdown(f"**To:** {m['to']} · **Subject:** {m['subject']}")
            st.code(m["body"], language=None)
        if not s["emails"]:
            st.caption("None yet")
ui.footer()
