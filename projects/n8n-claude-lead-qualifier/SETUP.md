# Setup

About 20 minutes. Requires **n8n 1.70+** (Slack *Send and Wait for Response* and Switch v3).

## 1. Import

n8n → **Workflows → Add workflow → ⋯ → Import from File** → `workflow.json`. Five nodes show credential warnings. That's expected.

## 2. Credentials

| Credential | Type | Used by | Notes |
|---|---|---|---|
| Anthropic | **Header Auth**: name `x-api-key`, value = your API key | Claude: Score & Draft | Keep the `anthropic-version: 2023-06-01` header in the node. |
| Slack | **Slack API** (bot token) | Slack: Approve Reply, Slack: Failure Alert | Bot scopes: `chat:write`. Create `#lead-approvals` and `#automation-alerts`, then `/invite` the bot to both. |
| HubSpot | **HubSpot App Token** (private app) | Both HubSpot nodes | Private app scopes: `crm.objects.contacts.read`, `crm.objects.contacts.write`. |
| Gmail | **Gmail OAuth2** | Gmail: Send Approved Reply | This account sends the reply to the prospect. |

## 3. Connect your form

Use the webhook's **Production URL** (`/webhook/lead-intake`). Send JSON with `name`, `email`, `company`, `budget`, `timeline`, `message`, an optional `source`, and a hidden empty `website` honeypot field.

For browser forms on a different domain, enable CORS for that origin in the Webhook node's options (*Allowed Origins*).

## 4. Test

1. Click **Test workflow**, then send the `curl` from the README to the *Test URL*.
2. You should get `202` back immediately, then a Slack message in `#lead-approvals`.
3. Click **Approve & Send**. Check that the contact appears in HubSpot and the reply arrives in the test inbox. *Use your own address as the lead email while testing.*
4. Send an invalid payload (no email) and you should get `400` with an `errors` array.
5. Send `"website": "x"` and the run should end at *Bot: Drop Silently* without calling Claude.
6. Break the Anthropic credential and you should get 4 retries, then a message in `#automation-alerts`.

## 5. Tuning

| What | Where |
|---|---|
| Qualification threshold (default 50) | **Route by Score** → second rule |
| Scoring rubric, reply tone and length | System prompt in the Claude node's JSON body |
| Fields Claude returns | The `input_schema` in the Claude node **and** the parser. Keep them in sync. |
| Approval timeout (default 48 h) | **Slack: Approve Reply** → Options → Limit Wait Time |
| Model | `claude-sonnet-5-5` in the Claude node body |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| 401 from Claude | Header name must be exactly `x-api-key` |
| "did not return a record_lead_assessment tool call" | `tool_choice` was removed or `max_tokens` is too low. Check the raw response in the execution |
| Slack approval never posts | Bot isn't in `#lead-approvals` or lacks `chat:write` |
| HubSpot 403 | Private app is missing the contacts write scope |
| Webhook returns nothing | The workflow isn't active (Production URL) or you're not listening (Test URL) |
