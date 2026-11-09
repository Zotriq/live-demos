"""Builds workflow.json from readable parts (JS in code/*.js, prompts inline).

    python build_workflow.py

Editing JavaScript inside a JSON string is error-prone, so the Code nodes live in
code/*.js (and are unit-tested there) and this script assembles the n8n export.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
CODE = ROOT / "code"


def uid(n: int) -> str:
    return f"c2000000-0000-4000-8000-{n:012d}"


def code_node(n, name, file, pos):
    return {"parameters": {"jsCode": (CODE / file).read_text()}, "id": uid(n), "name": name,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}


SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "decisions", "action_items", "risks"],
    "properties": {
        "summary": {"type": "string", "description": "3-5 sentence plain-English summary"},
        "decisions": {"type": "array", "items": {"type": "string"}},
        "action_items": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["task", "owner", "due_date", "priority"],
            "properties": {
                "task": {"type": "string", "description": "Imperative, specific, under 100 characters"},
                "owner": {"type": ["string", "null"], "description": "Attendee name exactly as given, or null"},
                "due_date": {"type": ["string", "null"], "description": "YYYY-MM-DD if a deadline was stated, else null"},
                "priority": {"type": "string", "enum": ["urgent", "high", "normal", "low"]},
            }}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM_PROMPT = (
    "You turn meeting transcripts into structured notes. Only include action items someone actually agreed "
    "to do. Never invent owners or deadlines: use null when the transcript doesn't say. Resolve relative dates "
    "(\"by Friday\") against the meeting date. Owners must be one of the attendees."
)

SUMMARIZE_BODY = (
    "={{ JSON.stringify({ model: 'gpt-4o-mini', temperature: 0, "
    "response_format: { type: 'json_schema', json_schema: { name: 'meeting_notes', strict: true, schema: "
    + json.dumps(SUMMARY_SCHEMA) + " } }, "
    "messages: [ { role: 'system', content: " + json.dumps(SYSTEM_PROMPT) + " }, "
    "{ role: 'user', content: 'Meeting: ' + $json.title + '\\nDate: ' + $json.date + "
    "'\\nAttendees: ' + $json.attendees.map(a => a.name).join(', ') + '\\n\\nTranscript:\\n' + $json.transcript } ] }) }}"
)

nodes = [
    {"parameters": {"httpMethod": "POST", "path": "meeting-notes", "responseMode": "responseNode", "options": {}},
     "id": uid(1), "name": "Meeting Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
     "position": [0, 300], "webhookId": uid(101)},
    code_node(2, "Validate Input", "validate_input.js", [220, 300]),
    {"parameters": {"respondWith": "json", "responseBody": "={{ JSON.stringify({ accepted: true, meeting: $json.title }) }}",
                    "options": {"responseCode": 202}},
     "id": uid(3), "name": "Respond 202", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [440, 300]},
    {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                                   "conditions": [{"id": uid(201), "leftValue": "={{ $json.transcript }}", "rightValue": "",
                                                   "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
                                   "combinator": "and"}, "options": {}},
     "id": uid(4), "name": "Has Transcript?", "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [660, 300]},
    {"parameters": {"url": "={{ $json.audio_url }}", "options": {"response": {"response": {"responseFormat": "file"}}}},
     "id": uid(5), "name": "Download Recording", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [880, 460]},
    {"parameters": {"method": "POST", "url": "https://api.openai.com/v1/audio/transcriptions",
                    "authentication": "predefinedCredentialType", "nodeCredentialType": "openAiApi",
                    "sendBody": True, "contentType": "multipart-form-data",
                    "bodyParameters": {"parameters": [
                        {"parameterType": "formBinaryData", "name": "file", "inputDataFieldName": "data"},
                        {"name": "model", "value": "whisper-1"}]},
                    "options": {"timeout": 300000}},
     "id": uid(6), "name": "Whisper: Transcribe", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1100, 460],
     "credentials": {"openAiApi": {"id": "REPLACE_WITH_CREDENTIAL_ID", "name": "OpenAI (placeholder)"}}},
    code_node(7, "Attach Transcript", "attach_transcript.js", [1320, 460]),
    {"parameters": {"method": "POST", "url": "https://api.openai.com/v1/chat/completions",
                    "authentication": "predefinedCredentialType", "nodeCredentialType": "openAiApi",
                    "sendBody": True, "specifyBody": "json", "jsonBody": SUMMARIZE_BODY, "options": {"timeout": 120000}},
     "id": uid(8), "name": "OpenAI: Summarize & Extract", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
     "position": [1540, 300], "onError": "continueErrorOutput",
     "credentials": {"openAiApi": {"id": "REPLACE_WITH_CREDENTIAL_ID", "name": "OpenAI (placeholder)"}}},
    code_node(9, "Parse & Map Owners", "parse_and_map.js", [1760, 300]),
    {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                                   "conditions": [{"id": uid(202), "leftValue": "={{ $json.skip === true }}", "rightValue": "",
                                                   "operator": {"type": "boolean", "operation": "false", "singleValue": True}}],
                                   "combinator": "and"}, "options": {}},
     "id": uid(17), "name": "Any Action Items?", "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1980, 300]},
    {"parameters": {"method": "POST", "url": "=https://api.clickup.com/api/v2/list/{{ $json.list_id }}/task",
                    "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
                    "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.clickup_task) }}",
                    "options": {"batching": {"batch": {"batchSize": 5, "batchInterval": 1000}}}},
     "id": uid(10), "name": "ClickUp: Create Task", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
     "position": [2200, 220], "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000,
     "credentials": {"httpHeaderAuth": {"id": "REPLACE_WITH_CREDENTIAL_ID", "name": "ClickUp token (placeholder)"}}},
    code_node(11, "Build Recap", "build_recap.js", [2420, 300]),
    {"parameters": {"select": "channel", "channelId": {"__rl": True, "mode": "name", "value": "#meeting-notes"},
                    "text": "={{ $json.slack_text }}", "otherOptions": {}},
     "id": uid(12), "name": "Slack: Post Recap", "type": "n8n-nodes-base.slack", "typeVersion": 2.3, "position": [2640, 300],
     "webhookId": uid(102), "credentials": {"slackApi": {"id": "REPLACE_WITH_CREDENTIAL_ID", "name": "Slack (placeholder)"}}},
    {"parameters": {"select": "channel", "channelId": {"__rl": True, "mode": "name", "value": "#automation-alerts"},
                    "text": "=:rotating_light: Meeting notes failed for *{{ $('Validate Input').first().json.title }}* "
                            "(execution {{ $execution.id }}).\nError: {{ $json.error?.message || 'see execution log' }}",
                    "otherOptions": {}},
     "id": uid(13), "name": "Slack: Failure Alert", "type": "n8n-nodes-base.slack", "typeVersion": 2.3, "position": [1760, 520],
     "webhookId": uid(103), "credentials": {"slackApi": {"id": "REPLACE_WITH_CREDENTIAL_ID", "name": "Slack (placeholder)"}}},
    {"parameters": {"content": "## 1. Intake\nPOST a transcript (Zoom, Fireflies, Otter, Teams) **or** an `audio_url`.\n"
                               "Returns 202 right away; the rest runs in the background.", "height": 220, "width": 680},
     "id": uid(14), "name": "Note: Intake", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [-40, 40]},
    {"parameters": {"content": "## 2. Understand\nNo transcript? Download the recording and transcribe it with Whisper.\n"
                               "Then GPT returns **strict JSON**: summary, decisions, action items, risks.",
                    "height": 220, "width": 760},
     "id": uid(15), "name": "Note: AI", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [840, 40]},
    {"parameters": {"content": "## 3. Act\nOwners are mapped to ClickUp users, tasks are created (with retries),\n"
                               "and a recap with task links goes to Slack.", "height": 220, "width": 1100},
     "id": uid(16), "name": "Note: Act", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [1740, 40]},
]


def link(*targets):
    return [[{"node": t, "type": "main", "index": 0}] for t in targets]


connections = {
    "Meeting Webhook": {"main": link("Validate Input")},
    "Validate Input": {"main": link("Respond 202")},
    "Respond 202": {"main": link("Has Transcript?")},
    "Has Transcript?": {"main": [[{"node": "OpenAI: Summarize & Extract", "type": "main", "index": 0}],
                                 [{"node": "Download Recording", "type": "main", "index": 0}]]},
    "Download Recording": {"main": link("Whisper: Transcribe")},
    "Whisper: Transcribe": {"main": link("Attach Transcript")},
    "Attach Transcript": {"main": link("OpenAI: Summarize & Extract")},
    "OpenAI: Summarize & Extract": {"main": [[{"node": "Parse & Map Owners", "type": "main", "index": 0}],
                                             [{"node": "Slack: Failure Alert", "type": "main", "index": 0}]]},
    "Parse & Map Owners": {"main": link("Any Action Items?")},
    "Any Action Items?": {"main": [[{"node": "ClickUp: Create Task", "type": "main", "index": 0}],
                                   [{"node": "Build Recap", "type": "main", "index": 0}]]},
    "ClickUp: Create Task": {"main": link("Build Recap")},
    "Build Recap": {"main": link("Slack: Post Recap")},
}

workflow = {
    "name": "Meeting Notes → ClickUp Tasks + Slack Recap",
    "nodes": nodes,
    "pinData": {},
    "connections": connections,
    "active": False,
    "settings": {"executionOrder": "v1"},
    "tags": [],
    "meta": {"templateCredsSetupCompleted": False},
}

if __name__ == "__main__":
    (ROOT / "workflow.json").write_text(json.dumps(workflow, indent=2) + "\n")
    print(f"workflow.json: {len(nodes)} nodes")
