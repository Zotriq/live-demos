"""Glow Desk: one sandboxed salon per visitor, driven by the real whatsapp-ai-agent webhook server."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lib import llm, ui  # noqa: E402

ui.project_path("whatsapp-ai-agent")
from fastapi.testclient import TestClient  # noqa: E402
from wa_agent.agent import OpenAIChatModel  # noqa: E402
from wa_agent.app import create_app  # noqa: E402
from wa_agent.store import Store  # noqa: E402
from wa_agent.tools import BUSINESS, Salon  # noqa: E402

TZ = ZoneInfo(BUSINESS["timezone"])
SECRET, VERIFY, ADMIN = "glow-app-secret", "glow-verify-token", "glow-admin-token"
SERVICES = BUSINESS["services"]
REPO = "https://github.com/Zotriq/whatsapp-ai-agent"

EXTRA = """
CREATE TABLE IF NOT EXISTS msg_meta (msg_id INTEGER PRIMARY KEY, kind TEXT NOT NULL);       -- staff | system
CREATE TABLE IF NOT EXISTS booking_meta (code TEXT PRIMARY KEY, source TEXT NOT NULL, created_at TEXT);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS webhooks (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, method TEXT, path TEXT,
    status INTEGER, detail TEXT, ms INTEGER);
"""

URDU = re.compile(r"[؀-ۿ]")
ROMAN = {"hai", "kal", "baje", "kya", "mujhe", "ho", "sakta", "sakti", "karna", "chahiye", "shaam", "aaj", "kitne", "kitna",
         "hain", "nahi", "theek", "acha", "bhai", "mera", "meri", "naam", "ko", "ka", "ki", "ke", "aap", "apka", "kab", "salam"}


def price_rs(service: str) -> int:
    digits = re.sub(r"[^0-9]", "", SERVICES[service]["price"])
    return int(digits) if digits else 0


def language(text: str) -> str:
    if URDU.search(text or ""):
        return "Urdu"
    words = set(re.findall(r"[a-z]+", (text or "").lower()))
    return "Roman Urdu" if len(words & ROMAN) >= 2 else "English"


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def to_local(iso: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(iso)
    if t.tzinfo is None:
        return t
    return t.astimezone(TZ).replace(tzinfo=None)


def local_now() -> dt.datetime:
    return dt.datetime.now(TZ).replace(tzinfo=None)


def to_utc_iso(local: dt.datetime) -> str:
    return local.replace(tzinfo=TZ).astimezone(dt.timezone.utc).isoformat()


class LazyModel:
    """Creates the Groq-backed client on first use, so the app loads even before a key is configured."""

    def __init__(self):
        self._model = None

    def complete(self, messages, tools):
        if self._model is None:
            self._model = OpenAIChatModel(llm.groq_key(), llm.SMART, llm.GROQ_BASE_URL)
        return self._model.complete(messages, tools)


class Sandbox:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="glowdesk-"))
        self.store = Store(self.dir / "glow.db")
        self.db = self.store.conn
        self.db.executescript(EXTRA)
        self.salon = Salon(self.store, now=local_now)
        self.auto_reply = True
        self.last_run: dict | None = None
        self.model = LazyModel()
        self.app = create_app(self.store, self.model, self, app_secret=SECRET, verify_token=VERIFY,
                              admin_token=ADMIN, notify_staff=self.alert, salon=self.salon)
        self.client = TestClient(self.app)
        from . import seed

        seed.populate(self)

    # ---- the agent's outgoing side (implements the project's Sender protocol) ----
    def send_text(self, to: str, body: str) -> None:
        last = self.db.execute("SELECT id, content FROM messages WHERE phone = ? ORDER BY id DESC LIMIT 1", (to,)).fetchone()
        if not last or (json.loads(last["content"]).get("content") or "").strip() != body.strip():
            # e.g. the "unsupported message" or error fallback: sent without going through the model
            self.add_message(to, {"role": "assistant", "content": body}, kind="system")
        self.event("whatsapp", f"Reply sent to +{to}")

    def alert(self, text: str) -> None:
        self.event("slack", text)

    # ---- helpers ----
    def event(self, kind: str, text: str, at: str | None = None) -> None:
        self.db.execute("INSERT INTO events (at, kind, text) VALUES (?, ?, ?)", (at or now_utc().isoformat(), kind, text))

    def add_message(self, phone: str, message: dict, at: str | None = None, kind: str | None = None) -> int:
        cur = self.db.execute("INSERT INTO messages (phone, role, content, at) VALUES (?, ?, ?, ?)",
                              (phone, message["role"], json.dumps(message), at or now_utc().isoformat()))
        if kind:
            self.db.execute("INSERT INTO msg_meta VALUES (?, ?)", (cur.lastrowid, kind))
        return cur.lastrowid

    def log_webhook(self, method: str, path: str, status: int, detail: str, ms: int) -> None:
        self.db.execute("INSERT INTO webhooks (at, method, path, status, detail, ms) VALUES (?, ?, ?, ?, ?, ?)",
                        (now_utc().isoformat(), method, path, status, detail, ms))

    # ---- customer side: exactly what Meta would POST ----
    def payload(self, phone: str, name: str, text: str, wamid: str | None = None) -> bytes:
        return json.dumps({"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp", "metadata": {"phone_number_id": "PNID"},
            "contacts": [{"wa_id": phone, "profile": {"name": name}}],
            "messages": [{"from": phone, "id": wamid or f"wamid.{uuid.uuid4().hex}", "timestamp": str(int(time.time())),
                          "type": "text", "text": {"body": text}}]}}]}]}).encode()

    @staticmethod
    def sign(body: bytes) -> str:
        return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    def customer_says(self, phone: str, name: str, text: str) -> dict:
        if not self.auto_reply:
            self.store.conversation(phone, name)
            self.store.set_mode(phone, "human")
        before = self.db.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
        events_before = self.db.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()[0]
        body = self.payload(phone, name, text)
        started = time.time()
        resp = self.client.post("/webhook", content=body, headers={"X-Hub-Signature-256": self.sign(body),
                                                                    "Content-Type": "application/json"})
        ms = int((time.time() - started) * 1000)
        self.log_webhook("POST", "/webhook", resp.status_code, "message from +" + phone + " · signature ✓", ms)
        new = [dict(r) for r in self.db.execute("SELECT * FROM messages WHERE id > ? AND phone = ? ORDER BY id", (before, phone))]
        alerts = [r["text"] for r in self.db.execute("SELECT text FROM events WHERE id > ? AND kind = 'slack'", (events_before,))]
        self.last_run = {"phone": phone, "text": text, "status": resp.status_code, "ms": ms, "messages": new, "alerts": alerts}
        return self.last_run

    # ---- staff side ----
    def staff_reply(self, phone: str, text: str) -> None:
        self.add_message(phone, {"role": "assistant", "content": text}, kind="staff")
        self.event("staff", f"Staff replied to +{phone}")

    def take_over(self, phone: str) -> None:
        self.store.set_mode(phone, "human")
        self.event("staff", f"Staff took over the chat with +{phone}")

    def release(self, phone: str) -> int:
        started = time.time()
        resp = self.client.post(f"/admin/release/{phone}", headers={"X-Admin-Token": ADMIN})
        self.log_webhook("POST", f"/admin/release/{phone}", resp.status_code, json.dumps(resp.json()), int((time.time() - started) * 1000))
        self.event("staff", f"Chat with +{phone} handed back to the AI")
        return resp.status_code

    def book_manually(self, phone: str, name: str, service: str, start: dt.datetime, notify: bool) -> str:
        end = start + dt.timedelta(minutes=SERVICES[service]["minutes"])
        code = self.store.insert_booking(phone, name, service, start, end)
        self.db.execute("INSERT INTO booking_meta VALUES (?, 'Front desk', ?)", (code, now_utc().isoformat()))
        self.store.conversation(phone, name)
        self.event("booking", f"Front desk booked {SERVICES[service]['label']} for {name}")
        if notify:
            self.add_message(phone, {"role": "assistant", "content":
                f"Hi {name.split()[0]}! Your {SERVICES[service]['label']} is booked for {start:%A %d %B at %-I:%M %p}. "
                f"Booking code: *{code}*. Reply here if you need to change it."}, kind="system")
            self.event("whatsapp", f"Confirmation sent to +{phone}")
        return code

    def cancel(self, code: str) -> None:
        self.db.execute("UPDATE bookings SET status = 'cancelled' WHERE code = ?", (code,))
        self.event("booking", f"Booking {code} cancelled by the front desk")

    # ---- reads ----
    def messages(self, phone: str) -> list[dict]:
        rows = self.db.execute("SELECT m.id, m.content, m.at, mm.kind FROM messages m LEFT JOIN msg_meta mm ON mm.msg_id = m.id "
                               "WHERE m.phone = ? ORDER BY m.id", (phone,))
        out = []
        for r in rows:
            msg = json.loads(r["content"])
            out.append({"id": r["id"], "role": msg["role"], "content": msg.get("content"), "tool_calls": msg.get("tool_calls") or [],
                        "at": to_local(r["at"]), "kind": r["kind"]})
        return out

    def conversations(self) -> list[dict]:
        out = []
        for c in self.db.execute("SELECT * FROM conversations"):
            last = self.db.execute("SELECT content, at, role FROM messages WHERE phone = ? AND role != 'tool' "
                                   "ORDER BY id DESC LIMIT 20", (c["phone"],)).fetchall()
            last_text, last_at, first_user = "", None, ""
            for r in last:
                m = json.loads(r["content"])
                if m.get("content"):
                    last_text, last_at = m["content"], to_local(r["at"])
                    break
            fu = self.db.execute("SELECT content FROM messages WHERE phone = ? AND role = 'user' ORDER BY id LIMIT 1", (c["phone"],)).fetchone()
            if fu:
                first_user = json.loads(fu["content"]).get("content") or ""
            if last_at is None:
                continue
            out.append({"phone": c["phone"], "name": c["name"] or "+" + c["phone"], "mode": c["mode"], "last_text": last_text,
                        "last_at": last_at, "language": language(first_user)})
        return sorted(out, key=lambda c: (c["mode"] != "human", -c["last_at"].timestamp()))

    def bookings(self) -> pd.DataFrame:
        rows = self.db.execute("SELECT b.*, COALESCE(bm.source, 'AI agent') AS source FROM bookings b "
                               "LEFT JOIN booking_meta bm ON bm.code = b.code").fetchall()
        df = pd.DataFrame([dict(r) for r in rows], columns=["code", "phone", "name", "service", "starts_at", "ends_at", "status", "source"])
        if df.empty:
            return df.assign(start=pd.Series(dtype="datetime64[ns]"), end=pd.Series(dtype="datetime64[ns]"), label="", price=0, state="")
        df["start"] = pd.to_datetime(df["starts_at"])
        df["end"] = pd.to_datetime(df["ends_at"])
        df["label"] = df["service"].map(lambda s: SERVICES[s]["label"])
        df["price"] = df["service"].map(price_rs)
        now = local_now()
        df["state"] = [("Cancelled" if s == "cancelled" else "Completed" if e <= now else "In progress" if st_ <= now else "Upcoming")
                       for s, st_, e in zip(df["status"], df["start"], df["end"])]
        return df.sort_values("start")

    def events(self, limit: int = 30) -> list[dict]:
        return [{"at": to_local(r["at"]), "kind": r["kind"], "text": r["text"]}
                for r in self.db.execute("SELECT * FROM events ORDER BY at DESC, id DESC LIMIT ?", (limit,))]

    def webhook_log(self) -> pd.DataFrame:
        rows = [dict(r) for r in self.db.execute("SELECT * FROM webhooks ORDER BY id DESC")]
        for r in rows:
            r["at"] = to_local(r["at"]).strftime("%H:%M:%S")
        return pd.DataFrame(rows, columns=["at", "method", "path", "status", "ms", "detail"])

    def reply_seconds(self, since: dt.datetime | None = None) -> list[float]:
        """Seconds between each customer message and the bot's answer."""
        out, pending = [], {}
        for r in self.db.execute("SELECT m.phone, m.content, m.at, mm.kind FROM messages m LEFT JOIN msg_meta mm ON mm.msg_id = m.id ORDER BY m.id"):
            msg = json.loads(r["content"])
            at = to_local(r["at"])
            if msg["role"] == "user":
                pending.setdefault(r["phone"], at)
            elif msg["role"] == "assistant" and msg.get("content") and not msg.get("tool_calls"):
                start = pending.pop(r["phone"], None)
                if start and r["kind"] is None and (since is None or at >= since):
                    out.append((at - start).total_seconds())
        return out


def sandbox() -> Sandbox:
    if "glow" not in st.session_state:
        with st.spinner("Setting up your private copy of the salon…"):
            st.session_state.glow = Sandbox()
    return st.session_state.glow


def reset() -> None:
    st.session_state.pop("glow", None)
    st.session_state.pop("inbox_sel", None)
