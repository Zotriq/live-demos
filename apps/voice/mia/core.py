"""Smileline: the voice-ai-receptionist project as a dental clinic's call console.

Live calls run the real loop: speech-to-text (Whisper), the model with the project's Vapi tools, the project's
FastAPI tool server (via Vapi-format webhooks), text-to-speech. The call history is sample data."""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys
import tempfile
import time
import uuid
import wave
from pathlib import Path

import pandas as pd
import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lib import llm, ui  # noqa: E402

REPO_DIR = ui.project_path("voice-ai-receptionist")
from fastapi.testclient import TestClient  # noqa: E402
from receptionist.scheduling import AppointmentBook  # noqa: E402
from receptionist.server import create_app  # noqa: E402

REPO = "https://github.com/Zotriq/voice-ai-receptionist"
SECRET = "smileline-vapi-secret"
PROMPT = (REPO_DIR / "vapi" / "system_prompt.md").read_text()
TOOLS = [{"type": t["type"], "function": t["function"]} for t in json.loads((REPO_DIR / "vapi" / "tools.json").read_text())]
TOOLS.append({"type": "function", "function": {
    "name": "transfer_to_front_desk", "description": "Transfer the caller to a human at the front desk.",
    "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}})
GREETING = "Thank you for calling Bright Smile Dental, this is Mia. How can I help you today?"
VOICES = {"hannah": "Hannah (warm)", "autumn": "Autumn (calm)", "diana": "Diana (bright)"}
OUTCOMES = ["Booked", "Cancelled", "Question answered", "Transferred", "Looked up appointment", "No action"]

EXTRA = """
CREATE TABLE IF NOT EXISTS call_meta (
    call_id TEXT PRIMARY KEY, started_at TEXT, seconds INTEGER, outcome TEXT, caller_name TEXT,
    turns TEXT, tools TEXT, transferred TEXT, live INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS appt_meta (code TEXT PRIMARY KEY, source TEXT);
CREATE TABLE IF NOT EXISTS hooks (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, kind TEXT, status INTEGER, detail TEXT);
"""


def client():
    from openai import OpenAI

    return OpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL)


class Sandbox:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="smileline-"))
        self.book = AppointmentBook(self.dir / "clinic.db")
        self.clinic = self.book.clinic
        self.db = self.book.conn
        self.db.executescript(EXTRA)
        self.server = TestClient(create_app(self.book, secret=SECRET, slack_webhook=""))
        self.voice = "hannah"
        self.call: dict | None = None
        self.selected_call: str | None = None
        from . import seed

        seed.populate(self)

    def now(self) -> dt.datetime:
        return self.clinic.now().replace(microsecond=0)

    def log_hook(self, kind: str, status: int, detail: str) -> None:
        self.db.execute("INSERT INTO hooks (at, kind, status, detail) VALUES (?, ?, ?, ?)",
                        (self.now().isoformat(), kind, status, detail))

    # ---------------- live call ----------------
    def start_call(self, caller: str, number: str) -> dict:
        self.call = {"id": "call_" + uuid.uuid4().hex[:10], "caller": caller, "number": number, "started": self.now(),
                     "t0": time.time(), "messages": [], "turns": [("assistant", GREETING)], "tools": [], "audio": None,
                     "transferred": None, "ended": False}
        self.call["audio"] = self.speak(GREETING)
        return self.call

    def system_prompt(self) -> str:
        today = self.clinic.now().strftime("%A, %B %d, %Y")
        return re.sub(r"\{\{.*?\}\}", today, PROMPT) + (
            f"\n\nThe caller's number (from caller ID) is {self.call['number']}. Confirm it instead of asking for it.")

    def speak(self, text: str) -> bytes | None:
        """Orpheus TTS on Groq, sentence chunks of under 200 characters."""
        if not llm.groq_key():
            return None
        try:
            chunks, cur = [], ""
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if len(cur) + len(sentence) > 190 and cur:
                    chunks.append(cur)
                    cur = ""
                cur = (cur + " " + sentence).strip()
            chunks.append(cur)
            frames, params = [], None
            for chunk in chunks:
                audio = client().audio.speech.create(model=llm.TTS, voice=self.voice, input=chunk[:200], response_format="wav").read()
                with wave.open(io.BytesIO(audio)) as w:
                    params = params or w.getparams()
                    frames.append(w.readframes(w.getnframes()))
            out = io.BytesIO()
            with wave.open(out, "wb") as w:
                w.setparams(params._replace(nframes=0))
                for f in frames:
                    w.writeframes(f)
            return out.getvalue()
        except Exception as exc:  # noqa: BLE001  the text reply still works
            self.call["tts_error"] = str(exc)[:200]
            return None

    def transcribe(self, audio: bytes) -> str:
        return client().audio.transcriptions.create(model=llm.WHISPER, file=("speech.wav", audio)).text.strip()

    def vapi_tool(self, call) -> str:
        body = {"message": {"type": "tool-calls", "call": {"id": self.call["id"]},
                            "toolCallList": [{"id": call.id, "type": "function", "function": {
                                "name": call.function.name, "arguments": json.loads(call.function.arguments or "{}")}}]}}
        started = time.time()
        resp = self.server.post("/vapi/webhook", json=body, headers={"x-vapi-secret": SECRET})
        result = resp.json()["results"][0]
        text = result.get("result") or result.get("error") or ""
        self.log_hook("tool-calls", resp.status_code, f"{call.function.name} · {int((time.time() - started) * 1000)} ms")
        self.call["tools"].append({"name": call.function.name, "args": call.function.arguments, "result": text})
        return text

    def say(self, text: str) -> None:
        c = self.call
        c["turns"].append(("user", text))
        if not c["messages"]:
            c["messages"] = [{"role": "system", "content": self.system_prompt()}, {"role": "assistant", "content": GREETING}]
        c["messages"].append({"role": "user", "content": text})
        msg = None
        for _ in range(5):
            msg = client().chat.completions.create(model=llm.SMART, messages=c["messages"], tools=TOOLS, temperature=0.3).choices[0].message
            entry = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = [{"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}}
                                       for t in msg.tool_calls]
            c["messages"].append(entry)
            if not msg.tool_calls:
                break
            for call in msg.tool_calls:
                if call.function.name == "transfer_to_front_desk":
                    reason = json.loads(call.function.arguments or "{}").get("reason", "")
                    c["transferred"] = reason
                    c["tools"].append({"name": "transfer_to_front_desk", "args": call.function.arguments,
                                       "result": "Vapi transfers the call to the front desk line"})
                    result = "Transferring now."
                else:
                    result = self.vapi_tool(call)
                c["messages"].append({"role": "tool", "tool_call_id": call.id, "content": result})
        answer = ((msg.content if msg else "") or "").strip() or "Sorry, could you say that again?"
        c["turns"].append(("assistant", answer))
        c["audio"] = self.speak(answer)

    def hang_up(self) -> str:
        c = self.call
        lines = "\n".join(f"{'AI' if r == 'assistant' else 'User'}: {t}" for r, t in c["turns"])
        summary = client().chat.completions.create(model=llm.FAST, messages=[
            {"role": "system", "content": "Summarise this dental clinic phone call in 2 sentences for the front desk."},
            {"role": "user", "content": lines}]).choices[0].message.content
        resp = self.server.post("/vapi/webhook", headers={"x-vapi-secret": SECRET}, json={"message": {
            "type": "end-of-call-report", "endedReason": "assistant-forwarded-call" if c["transferred"] else "customer-ended-call",
            "call": {"id": c["id"], "customer": {"number": c["number"]}}, "analysis": {"summary": summary},
            "artifact": {"transcript": lines}}})
        self.log_hook("end-of-call-report", resp.status_code, f"call {c['id']} logged")
        names = [t["name"] for t in c["tools"]]
        outcome = ("Transferred" if c["transferred"] else "Booked" if "book_appointment" in names else
                   "Cancelled" if "cancel_appointment" in names else "Looked up appointment" if "find_appointment" in names else
                   "Question answered" if "get_clinic_info" in names or "check_availability" in names else "No action")
        for code, in self.db.execute("SELECT code FROM appointments WHERE call_id = ?", (c["id"],)).fetchall():
            self.db.execute("INSERT OR IGNORE INTO appt_meta VALUES (?, 'Mia (phone)')", (code,))
        self.db.execute("INSERT OR REPLACE INTO call_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)", (
            c["id"], c["started"].isoformat(), max(1, int(time.time() - c["t0"])), outcome, c["caller"],
            json.dumps(c["turns"]), json.dumps(c["tools"]), c["transferred"]))
        c["ended"] = True
        self.selected_call = c["id"]
        return summary

    # ---------------- reads ----------------
    def calls(self) -> pd.DataFrame:
        rows = self.db.execute("SELECT c.call_id, c.caller, c.ended_reason, c.summary, m.started_at, m.seconds, m.outcome, "
                               "m.caller_name, m.turns, m.tools, m.transferred, m.live FROM calls c "
                               "JOIN call_meta m ON m.call_id = c.call_id").fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        df["started"] = pd.to_datetime(df["started_at"])
        return df.sort_values("started", ascending=False).reset_index(drop=True)

    def appointments(self) -> pd.DataFrame:
        rows = self.db.execute("SELECT a.*, COALESCE(m.source, 'Mia (phone)') AS source FROM appointments a "
                               "LEFT JOIN appt_meta m ON m.code = a.code").fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        df["start"] = pd.to_datetime(df["starts_at"])
        df["end"] = pd.to_datetime(df["ends_at"])
        services = self.clinic.config["services"]
        df["label"] = df["service"].map(lambda s: services[s]["label"])
        now = self.now()
        df["state"] = ["Cancelled" if s == "cancelled" else "Completed" if e <= now else "Upcoming"
                       for s, e in zip(df["status"], df["end"])]
        return df.sort_values("start")

    def after_hours(self, t: dt.datetime) -> bool:
        h = self.clinic.open_hours(t.date())
        return not h or not (h[0] <= t < h[1])


def sandbox() -> Sandbox:
    if "smile" not in st.session_state:
        with st.spinner("Setting up your private copy of the clinic…"):
            st.session_state.smile = Sandbox()
    return st.session_state.smile


def reset() -> None:
    st.session_state.pop("smile", None)
