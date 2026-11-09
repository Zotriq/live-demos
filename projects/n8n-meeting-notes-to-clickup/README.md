# Meeting Notes → ClickUp Tasks (n8n + AI)

![tests](https://github.com/Zotriq/n8n-meeting-notes-to-clickup/actions/workflows/tests.yml/badge.svg)
![n8n](https://img.shields.io/badge/n8n-workflow-EA4B71?style=flat-square&logo=n8n&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-Whisper%20%2B%20GPT-412991?style=flat-square&logo=openai&logoColor=white)
![ClickUp](https://img.shields.io/badge/ClickUp-tasks-7B68EE?style=flat-square&logo=clickup&logoColor=white)
![Slack](https://img.shields.io/badge/Slack-recap-4A154B?style=flat-square&logo=slack&logoColor=white)

An n8n workflow that turns every meeting into **assigned ClickUp tasks and a Slack recap**, with nobody having
to write notes.

Send it a transcript (from Zoom, Fireflies, Otter or Teams) or just a link to the recording. It transcribes the
audio if needed, pulls out the summary, decisions, action items and risks, creates a ClickUp task for each action
item with the right **owner, due date and priority**, and posts a recap with task links to Slack.

## Workflow

```
Meeting Webhook ─► Validate Input ─► Respond 202 ─► Has Transcript?
                                                     │ yes                 │ no
                                                     │          Download Recording ─► Whisper: Transcribe ─► Attach Transcript
                                                     ▼                                                          │
                                       OpenAI: Summarize & Extract  ◄───────────────────────────────────────────┘
                                         │ (strict JSON schema)          └─ error ─► Slack: Failure Alert
                                         ▼
                                Parse & Map Owners ─► Any Action Items?
                                                        │ yes                        │ no
                                              ClickUp: Create Task (retries)         │
                                                        ▼                            ▼
                                                    Build Recap ─────────────► Slack: Post Recap
```

### What makes it reliable

- **Strict JSON output.** GPT must return a fixed schema (`summary`, `decisions`, `action_items[{task, owner, due_date, priority}]`, `risks`), and the workflow validates it again before using it.
- **No invented owners or deadlines.** The prompt forbids guessing. Owners must be attendees and are matched to ClickUp users by full name, then by unique first name. Unmatched owners are left unassigned and **flagged in the recap** instead of assigned to the wrong person.
- **Relative dates resolved.** "By Friday" becomes a real date based on the meeting date.
- **Responds immediately.** The webhook answers `202` before the slow AI steps, so Zoom or Fireflies never time out.
- **Retries and alerts.** ClickUp calls retry 3 times and are rate-limited (5 per second). If the AI step fails, an alert goes to `#automation-alerts`.
- **Meetings with no action items** still get a recap ("No action items were agreed").

## Example

Request ([`examples/sample_request.json`](examples/sample_request.json)):

```json
{
  "title": "Q4 launch sync",
  "date": "2026-11-09",
  "attendees": [{"name": "Sara Malik"}, {"name": "Omar Farooq"}, "Liam Smith"],
  "transcript": "Sara: Let's lock the launch date... Omar: I can finish the pricing page by Friday..."
}
```

Slack recap produced by the workflow's code from the sample AI response in
[`examples/sample_openai_response.json`](examples/sample_openai_response.json):

```
📝 Q4 launch sync (2026-11-09)
The team confirmed the December 1 launch. ...

Decisions
• Launch date stays December 1
• Annual discount is dropped for launch

Action items
• Finish the pricing page (Omar Farooq · due 2026-11-13)
• Send the migration guide to beta users (Liam · due 2026-11-11)
• Chase the payment provider for account approval (Omar · due 2026-11-09)
• Update the launch checklist (⚠️ no owner)

Risks / open questions
• Payment provider has not approved the account yet
```

## Setup

1. In n8n: **Workflows → Import from File → `workflow.json`**.
2. Create credentials and select them on the nodes:
   - **OpenAI**: used by *Whisper: Transcribe* and *OpenAI: Summarize & Extract*
   - **Header Auth** for ClickUp: name `Authorization`, value your ClickUp API token (`pk_...`)
   - **Slack**: for the recap and failure alert nodes
3. In **Parse & Map Owners**, set `DEFAULT_LIST_ID` and the `TEAM` map (attendee name → ClickUp user id; get ids from `GET https://api.clickup.com/api/v2/team`).
4. Activate the workflow and point your meeting tool's webhook (or a Zapier/Make step) at `POST /webhook/meeting-notes`.

## Development

The JavaScript for the Code nodes lives in [`code/`](code) so it can be read, reviewed and tested.
[`build_workflow.py`](build_workflow.py) assembles `workflow.json` from it.

```bash
python build_workflow.py   # rebuild workflow.json after editing code/*.js
npm test                   # 15 tests, Node 18+
```

The tests run every Code node with the same `$input`, `$()` and `$now` globals n8n provides. They cover input
validation, Whisper merge, owner and date mapping, priorities, per-request ClickUp lists, invalid AI output,
the recap text, and the no-action-items path. They also check the workflow itself: unique nodes, valid
connections, every node reachable, the error branch wired up, and no real credentials committed. CI also fails
if `workflow.json` is out of date with `code/`.

## License

MIT © Zohaib Tariq
