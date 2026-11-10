# Claude Lead Qualifier for n8n

**Webhook intake → validation & bot filter → Claude tool-use scoring → Slack approval → HubSpot + Gmail**

An n8n workflow that qualifies inbound leads with Claude, scores them 0–100, drafts a personalized reply, and only acts after a human approves the draft in Slack. Approved leads become HubSpot contacts and get the reviewed reply emailed to them automatically.

## Flow

```
POST /webhook/lead-intake
  └─ Validate & Normalize ──► invalid ──► 400 { errors }
        └─ valid ──► 202 Accepted (site never waits on the AI)
              └─ Honeypot check ──► bot ──► drop
                    └─ Claude (forced tool call, strict JSON schema)  ──► failure ──► Slack alert
                          └─ Parse & clamp output                    ──► failure ──► Slack alert
                                └─ Route by score
                                     ├─ spam        ──► discard
                                     ├─ score < 50  ──► HubSpot (subscriber / nurture)
                                     └─ score ≥ 50  ──► Slack Approve & Send / Decline (48 h timeout)
                                                          └─ approved ──► HubSpot upsert (lead) ──► Gmail reply to prospect
```

## What's different about this design

| Feature | How |
|---|---|
| **Website-ready intake** | Webhook with a `respondToWebhook` node: 400 + error list for bad payloads, instant 202 for good ones. |
| **Server-side validation** | Required fields, email format, trimming, lower-casing, 4 000-char message cap. |
| **Bot filtering** | Hidden `website` honeypot field. Bots are dropped *before* any Claude tokens are spent. |
| **Structured output via tool use** | Claude (`claude-sonnet-5-5`) is forced to call `record_lead_assessment` with a JSON schema: `category`, `score`, `reasoning`, `use_case`, `next_action`, `reply_subject`, `reply_body`. No regex-scraping of prose. |
| **Defense in depth** | The parser still whitelists enums, clamps the score, derives a P1/P2/P3 priority, and throws (→ alert) if the tool call is missing. |
| **Prompt-injection hardening** | Lead text is wrapped in `<lead>` tags and the system prompt declares it untrusted data. |
| **Score-based routing** | Spam is discarded, low scores go to HubSpot as nurture contacts with no human time spent, and only qualified leads reach a reviewer. |
| **Slack approvals** | Rich message with score, use case, suggested next step and the full draft; **Approve & Send** / **Decline** buttons; auto-expires after 48 h. |
| **Closes the loop** | After approval, the contact is upserted in HubSpot *and* the exact reviewed draft is emailed to the prospect. |
| **Resilience** | Claude: 4 tries, 4 s apart, 60 s timeout. HubSpot: 3 tries. Any Claude/parse failure posts to `#automation-alerts` with the execution ID. |

## Example request

```bash
curl -X POST https://YOUR-N8N/webhook/lead-intake \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Jane Doe",
    "email": "jane@acme.io",
    "company": "Acme Logistics",
    "budget": "$2k-5k",
    "timeline": "This month",
    "message": "We re-key 300 supplier invoices a week into Xero and want that automated.",
    "website": ""
  }'
# → 202 {"ok":true,"message":"Thanks - we will be in touch shortly."}
```

Keep `website` as a visually hidden input on your form. Humans leave it empty.

## Setup

See [SETUP.md](SETUP.md).

## Credits

This project started from the open-source [n8n + Claude lead pipeline](https://github.com/kelsonworks/n8n-claude-lead-pipeline) template by **Kelson Works** (MIT). That template used a form trigger, prompt-based JSON, Gmail approval and a Google Sheets log. This version was redesigned by **Zohaib Tariq**: webhook intake with validation and a honeypot, tool-use structured output with lead scoring, score-based routing, Slack approvals, a HubSpot CRM sync and automated sending of the approved reply.

## License

MIT. See [LICENSE](LICENSE).
