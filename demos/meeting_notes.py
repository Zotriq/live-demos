import datetime as dt
import json
import random

import streamlit as st
from openai import OpenAI

from lib import llm, n8n, ui

repo = ui.project_path("n8n-meeting-notes-to-clickup")
import build_workflow as wf  # noqa: E402  (the project's own workflow builder: prompts + schema)

CODE = {f.stem: f.read_text() for f in (repo / "code").glob("*.js")}
SAMPLE = json.loads((repo / "examples" / "sample_request.json").read_text())


def step(title: str, kind: str, data, expanded: bool = False) -> None:
    with st.expander(f"✅ {title}  ·  {kind}", expanded=expanded):
        st.json(data, expanded=1)


ui.header(
    "Meeting Notes → ClickUp (n8n)",
    "An n8n workflow that turns a meeting transcript or recording into a summary, decisions, and ClickUp tasks "
    "assigned to the right people with due dates, then posts a recap to Slack.",
    "n8n-meeting-notes-to-clickup",
    flow=["Webhook: transcript or recording", "Validate", "Whisper (if audio)", "GPT → strict JSON notes", "Map owners → ClickUp tasks", "Slack recap"],
    note="This page runs the workflow's own Code-node JavaScript with Node.js and sends the same AI request the "
         "workflow's HTTP node sends (using Groq here). ClickUp and Slack are shown, not called.",
)

if not n8n.available():
    st.error("Node.js isn't installed on this server, so the workflow's JavaScript nodes can't run.")
    st.stop()

c1, c2 = st.columns(2)
title = c1.text_input("Meeting title", SAMPLE["title"])
date = c2.date_input("Meeting date", dt.date.fromisoformat(SAMPLE["date"]))
attendees = st.text_input("Attendees (comma separated)", ", ".join(a if isinstance(a, str) else a["name"] for a in SAMPLE["attendees"]))
mode = st.radio("Input", ["Transcript", "Audio recording"], horizontal=True)
if mode == "Transcript":
    transcript = st.text_area("Transcript", SAMPLE["transcript"], height=150)
    audio = None
else:
    transcript = ""
    audio = st.audio_input("Record a short meeting (say who will do what, and by when)") or st.file_uploader("…or upload audio", type=["mp3", "wav", "m4a", "webm", "ogg"])
st.caption("Team members in ClickUp: Sara Malik, Omar Farooq, Liam Smith. Anyone else gets the task unassigned and flagged.")

if st.button("Run the workflow", type="primary"):
    try:
        body = {"title": title, "date": date.isoformat(), "attendees": [a.strip() for a in attendees.split(",") if a.strip()],
                "transcript": transcript, "audio_url": "https://example.com/recording" if audio else ""}
        st.markdown("**Execution**")
        step("Meeting Webhook", "POST /webhook/meeting-notes → 202 Accepted", body)
        meeting = n8n.run_code(CODE["validate_input"], input=[{"body": body}], today=date.isoformat())[0]
        step("Validate Input", "Code node", meeting)
        if audio:
            with st.spinner("Whisper is transcribing…"):
                text = OpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL).audio.transcriptions.create(
                    model=llm.WHISPER, file=(getattr(audio, "name", "meeting.wav"), audio.getvalue())).text
            step("Whisper: Transcribe", "HTTP node", {"text": text})
            meeting = n8n.run_code(CODE["attach_transcript"], input=[{"text": text}], nodes={"Validate Input": [meeting]})[0]
            step("Attach Transcript", "Code node", meeting)
        with st.spinner("AI is summarising and extracting action items…"):
            user = (f"Meeting: {meeting['title']}\nDate: {meeting['date']}\nAttendees: "
                    f"{', '.join(a['name'] for a in meeting['attendees'])}\n\nTranscript:\n{meeting['transcript']}")
            response = OpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL).chat.completions.create(
                model=llm.SMART, temperature=0,
                response_format={"type": "json_schema", "json_schema": {"name": "meeting_notes", "strict": True, "schema": wf.SUMMARY_SCHEMA}},
                messages=[{"role": "system", "content": wf.SYSTEM_PROMPT}, {"role": "user", "content": user}])
        ai = {"choices": [{"message": {"content": response.choices[0].message.content}}]}
        step("OpenAI: Summarize & Extract", "HTTP node, strict JSON schema", json.loads(ai["choices"][0]["message"]["content"]))
        tasks = n8n.run_code(CODE["parse_and_map"], input=[ai], nodes={"Validate Input": [meeting]})
        step("Parse & Map Owners", "Code node → one item per task", [{k: v for k, v in t.items() if k != "notes"} for t in tasks])
        created = []
        if not tasks[0].get("skip"):
            for t in tasks:
                tid = f"86{random.randint(10**6, 10**7)}"
                created.append({"id": tid, "url": f"https://app.clickup.com/t/{tid}", "name": t["clickup_task"]["name"]})
            step("ClickUp: Create Task", f"HTTP node · {len(created)} × POST /api/v2/list/{{list_id}}/task", created)
        recap = n8n.run_code(CODE["build_recap"], input=created or [{}],
                             nodes={"Parse & Map Owners": tasks, "Validate Input": [meeting]})[0]
        step("Build Recap", "Code node", recap)
        st.session_state.meeting_result = (tasks, recap)
    except n8n.NodeError as exc:
        st.error(f"A workflow node stopped the run: {exc}")
    except Exception as exc:
        llm.friendly_error(exc)

if st.session_state.get("meeting_result"):
    tasks, recap = st.session_state.meeting_result
    left, right = st.columns(2)
    with left:
        st.markdown("**ClickUp tasks**")
        for t in tasks:
            if t.get("skip"):
                st.caption("No action items were agreed.")
                continue
            task = t["clickup_task"]
            due = dt.datetime.fromtimestamp(task["due_date"] / 1000, dt.timezone.utc).date() if task.get("due_date") else "—"
            who = t["owner"] or "unassigned"
            st.markdown(f"- **{task['name']}**  \n  {who}{'' if t['assigned'] or not t['owner'] else ' ⚠️ not in ClickUp'} · due {due} · "
                        f"priority {['', 'urgent', 'high', 'normal', 'low'][task['priority']]}")
    with right:
        st.markdown("**Slack #meeting-notes**")
        st.code(recap["slack_text"], language=None, wrap_lines=True)
ui.footer()
