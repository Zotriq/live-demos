"""Operator OS: an AI growth operator's workspace for a small AI agency with several income streams.

Brightpath AI and everything in it is sample data. The AI features call a real language model (Groq)."""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys
import uuid
import wave
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lib import llm  # noqa: E402

AGENCY = "Brightpath AI"
STAGES = ["New lead", "Contacted", "Qualified", "Demo sent", "Call booked", "Won", "Lost"]
GROUPS = {
    "Agency (the money)": ["Agency retainers", "HVAC outreach", "Events consulting", "AI Twin offer"],
    "Lead source": ["YouTube"],
    "Background income": ["AI Music", "AI Books"],
}
STREAM_GROUP = {s: g for g, ss in GROUPS.items() for s in ss}
OWNER_TYPES = ["Contractor", "AI agent", "Automation", "Founder", "Operator"]


def now() -> dt.datetime:
    return dt.datetime.now().replace(second=0, microsecond=0)


def client():
    from openai import OpenAI

    return OpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL)


def ask_json(system: str, user: str, model: str | None = None) -> dict:
    """One model call that must return a JSON object."""
    messages = [{"role": "system", "content": system + "\nReply with one JSON object only."}, {"role": "user", "content": user}]
    try:
        resp = client().chat.completions.create(model=model or llm.SMART, temperature=0.4,
                                                response_format={"type": "json_object"}, messages=messages)
    except Exception as exc:  # noqa: BLE001  some models refuse JSON mode; ask plainly instead
        if "response_format" not in str(exc) and "json" not in str(exc).lower():
            raise
        resp = client().chat.completions.create(model=model or llm.SMART, temperature=0.4, messages=messages)
    text = resp.choices[0].message.content or "{}"
    try:
        return json.loads(text)
    except ValueError:
        return json.loads(re.search(r"\{.*\}", text, re.S).group(0))


def ask_text(system: str, messages: list[dict], model: str | None = None) -> str:
    resp = client().chat.completions.create(model=model or llm.SMART, temperature=0.5,
                                            messages=[{"role": "system", "content": system}] + messages)
    return (resp.choices[0].message.content or "").strip()


def speak(text: str, voice: str = "autumn") -> bytes | None:
    """Text to speech with Orpheus on Groq, in sentence chunks under 200 characters."""
    try:
        chunks, cur = [], ""
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if len(cur) + len(sentence) > 190 and cur:
                chunks.append(cur)
                cur = ""
            cur = (cur + " " + sentence).strip()
        chunks.append(cur)
        frames, params = [], None
        for chunk in chunks[:4]:
            audio = client().audio.speech.create(model=llm.TTS, voice=voice, input=chunk[:200], response_format="wav").read()
            with wave.open(io.BytesIO(audio)) as w:
                params = params or w.getparams()
                frames.append(w.readframes(w.getnframes()))
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setparams(params._replace(nframes=0))
            for f in frames:
                w.writeframes(f)
        return out.getvalue()
    except Exception:  # noqa: BLE001  voice is a bonus
        return None


class Workspace:
    def __init__(self):
        from . import seed

        self.leads: list[dict] = []
        self.tasks: list[dict] = []
        self.content: list[dict] = []
        self.demos: list[dict] = []
        self.events: list[dict] = []
        self.weekly: list[dict] = []
        self.jobs: list[dict] = []          # the HVAC client's booked visits
        self.brief: str | None = None
        self.active_lead: str | None = None
        seed.populate(self)

    def event(self, text: str, kind: str = "info", at: dt.datetime | None = None) -> None:
        self.events.insert(0, {"at": at or now(), "text": text, "kind": kind})

    def add_lead(self, **kw) -> dict:
        lead = {"id": "L" + uuid.uuid4().hex[:6].upper(), "created": now(), "stage": "New lead", "value": 0, "notes": "",
                "messages": [], "fields": {}, "first_reply_secs": None, "source": "", "stream": "HVAC outreach",
                "company": "", "name": "", "phone": "", "email": ""} | kw
        self.leads.insert(0, lead)
        return lead

    def lead(self, lid: str) -> dict | None:
        return next((l for l in self.leads if l["id"] == lid), None)


def ws() -> Workspace:
    if "ops" not in st.session_state:
        with st.spinner("Setting up your private copy of the workspace…"):
            st.session_state.ops = Workspace()
    return st.session_state.ops


def reset() -> None:
    st.session_state.pop("ops", None)


def need_key() -> bool:
    if not llm.groq_key():
        st.error("This deployment has no GROQ_API_KEY secret, so the AI features can't run.")
        return True
    return False
