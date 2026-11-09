import io
import json
import re
import tempfile
import uuid
import wave
from pathlib import Path

import streamlit as st
from fastapi.testclient import TestClient
from openai import OpenAI

from lib import llm, ui

repo = ui.project_path("voice-ai-receptionist")
from receptionist.scheduling import AppointmentBook  # noqa: E402
from receptionist.server import create_app  # noqa: E402

PROMPT = (repo / "vapi" / "system_prompt.md").read_text()
TOOLS = [{"type": t["type"], "function": t["function"]} for t in json.loads((repo / "vapi" / "tools.json").read_text())]
# In the real setup, call transfer is Vapi's built-in transferCall tool (it needs a phone line).
TOOLS.append({"type": "function", "function": {
    "name": "transfer_to_front_desk", "description": "Transfer the caller to a human at the front desk.",
    "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}})
GREETING = "Thank you for calling Bright Smile Dental, this is Mia. How can I help you today?"
VOICE = "hannah"


def call_state():
    if "voice" not in st.session_state:
        book = AppointmentBook(Path(tempfile.mkdtemp()) / "clinic.db")
        st.session_state.voice = {
            "id": "demo-" + uuid.uuid4().hex[:8], "book": book,
            "server": TestClient(create_app(book, secret="demo-secret", slack_webhook="")),
            "messages": [], "transcript": [("assistant", GREETING)], "webhooks": [], "audio": None,
            "ended": False, "transferred": None,
        }
    return st.session_state.voice


def client() -> OpenAI:
    return OpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL)


def system_prompt(c) -> str:
    today = c["book"].clinic.now().strftime("%A, %B %d, %Y")
    return re.sub(r"\{\{.*?\}\}", today, PROMPT)


def speak(text: str) -> bytes | None:
    """Orpheus TTS on Groq, in chunks of whole sentences (it takes short inputs)."""
    chunks, cur = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(cur) + len(sentence) > 190 and cur:
            chunks.append(cur)
            cur = ""
        cur = (cur + " " + sentence).strip()
    chunks.append(cur)
    frames, params = [], None
    for chunk in chunks:
        audio = client().audio.speech.create(model=llm.TTS, voice=VOICE, input=chunk[:200], response_format="wav").read()
        with wave.open(io.BytesIO(audio)) as w:
            params = params or w.getparams()
            frames.append(w.readframes(w.getnframes()))
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setparams(params)
        for f in frames:
            w.writeframes(f)
    return out.getvalue()


def vapi_tool_call(c, call: dict) -> str:
    """Send the tool call to the real server in Vapi's webhook format."""
    body = {"message": {"type": "tool-calls", "call": {"id": c["id"]},
                        "toolCallList": [{"id": call.id, "type": "function", "function": {
                            "name": call.function.name, "arguments": json.loads(call.function.arguments or "{}")}}]}}
    resp = c["server"].post("/vapi/webhook", json=body, headers={"x-vapi-secret": "demo-secret"})
    result = resp.json()["results"][0]
    c["webhooks"].append((call.function.name, call.function.arguments, result.get("result") or result.get("error")))
    return result.get("result") or result.get("error") or ""


def turn(c, text: str) -> None:
    c["transcript"].append(("user", text))
    if not c["messages"]:
        c["messages"] = [{"role": "system", "content": system_prompt(c)}, {"role": "assistant", "content": GREETING}]
    c["messages"].append({"role": "user", "content": text})
    for _ in range(5):
        resp = client().chat.completions.create(model=llm.SMART, messages=c["messages"], tools=TOOLS, temperature=0.3)
        msg = resp.choices[0].message
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
                c["webhooks"].append(("transfer_to_front_desk", call.function.arguments, "Vapi transfers the call to the front desk line"))
                result = "Transferring now."
            else:
                result = vapi_tool_call(c, call)
            c["messages"].append({"role": "tool", "tool_call_id": call.id, "content": result})
    answer = (msg.content or "").strip() or "Sorry, could you say that again?"
    c["transcript"].append(("assistant", answer))
    try:
        c["audio"] = speak(answer)
    except Exception:
        c["audio"] = None  # voice is a bonus; the text reply still shows


def hang_up(c) -> None:
    lines = "\n".join(f"{'AI' if r == 'assistant' else 'User'}: {t}" for r, t in c["transcript"])
    summary = client().chat.completions.create(model=llm.FAST, messages=[
        {"role": "system", "content": "Summarise this dental clinic phone call in 2 sentences for the front desk."},
        {"role": "user", "content": lines}]).choices[0].message.content
    c["server"].post("/vapi/webhook", headers={"x-vapi-secret": "demo-secret"}, json={"message": {
        "type": "end-of-call-report", "endedReason": "customer-ended-call", "call": {"id": c["id"], "customer": {"number": "+1 555 0100"}},
        "analysis": {"summary": summary}, "artifact": {"transcript": lines}}})
    c["ended"] = True


ui.header(
    "Voice AI Receptionist",
    "Mia answers a dental clinic's phone 24/7: she checks the real appointment book, books and cancels, answers "
    "questions from the clinic's own info, and transfers to staff when needed. Every call is logged with a summary.",
    "voice-ai-receptionist",
    flow=["Caller speaks", "Speech → text (Whisper)", "AI decides + calls tools", "Tool server: real bookings", "Spoken reply"],
    note="In production this runs on a phone number through Vapi. Here your browser microphone is the phone: "
         "the page plays Vapi's part and sends the same tool-call webhooks to the project's real server.",
)

c = call_state()
left, right = st.columns([3, 2])
with left:
    for role, text in c["transcript"]:
        with st.chat_message("assistant" if role == "assistant" else "user", avatar="🦷" if role == "assistant" else "🧑"):
            st.markdown(text)
    if c["audio"]:
        st.audio(c["audio"], format="audio/wav", autoplay=True)
    if c["transferred"]:
        st.info(f"📞 Call transferred to the front desk ({c['transferred']}).")
    if c["ended"]:
        st.success("Call ended. The end-of-call report was sent to the server and logged (see the right).")
    else:
        recording = st.audio_input("Hold to talk: press record, speak, then stop", key=f"rec_{len(c['transcript'])}")
        typed = st.chat_input("…or type what you'd say")
        try:
            if recording is not None:
                with st.spinner("Transcribing…"):
                    heard = client().audio.transcriptions.create(model=llm.WHISPER, file=("speech.wav", recording.getvalue())).text.strip()
                if heard:
                    with st.spinner("Mia is thinking…"):
                        turn(c, heard)
                st.rerun()
            if typed:
                with st.spinner("Mia is thinking…"):
                    turn(c, typed)
                st.rerun()
        except Exception as exc:
            llm.friendly_error(exc)
        st.caption("Try: “I'd like a check-up next Tuesday afternoon” · “What are your hours?” · “I broke a tooth, it really hurts”")
    a, b = st.columns(2)
    if not c["ended"] and len(c["transcript"]) > 1 and a.button("Hang up", type="primary"):
        try:
            hang_up(c)
        except Exception as exc:
            llm.friendly_error(exc)
        st.rerun()
    if b.button("New call"):
        del st.session_state["voice"]
        st.rerun()

with right:
    st.markdown("**Behind the scenes**")
    with st.expander(f"Webhooks to the tool server ({len(c['webhooks'])})", expanded=True):
        for name, args, result in c["webhooks"]:
            st.markdown(f"`{name}({args})`\n\n→ {result}")
        if not c["webhooks"]:
            st.caption("None yet")
    appts = c["server"].get("/appointments").json()
    with st.expander(f"Appointment book ({len(appts)})", expanded=bool(appts)):
        st.table([{k: a[k] for k in ("code", "patient", "service", "starts_at", "status") if k in a} for a in appts]) if appts else st.caption("No bookings yet")
    calls = c["server"].get("/calls").json()
    with st.expander(f"Call log ({len(calls)})", expanded=bool(calls)):
        for call in calls:
            st.markdown(f"**{call['call_id']}** · {call['ended_reason']}\n\n{call['summary']}")
        if not calls:
            st.caption("Logged when the call ends")
ui.footer()
