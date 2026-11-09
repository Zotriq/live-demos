# AI Lead Qualification Agent

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15+-000000?style=flat-square&logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791?style=flat-square&logo=postgresql&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=flat-square&logo=openai&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Overview

The **AI Lead Qualification Agent** is a production-ready, AI-powered system that automates the entire lead qualification lifecycle. It receives inbound leads from multiple sources, scores them using a hybrid rules-and-AI engine, classifies each lead as **hot / warm / cold / unqualified**, generates personalized follow-up emails, and routes qualified leads into your sales workflows — all with a human-in-the-loop approval gate before any email is sent.

Supported intake sources include website forms, webhooks, CRMs, Google Sheets, Airtable, and n8n automation workflows. Sales teams get a real-time dashboard to review leads, approve or reject AI-drafted emails, and monitor pipeline analytics without touching any code.

---

## Key Features

- **Multi-source lead intake** — website forms, webhooks, CRM sync, Google Sheets, Airtable, and n8n
- **Hybrid scoring engine** — business rules (budget, title, industry, intent, etc.) combined with GPT-4o-mini analysis
- **AI-powered lead analysis** — OpenAI evaluates lead quality, extracts intent signals, and generates a natural-language summary
- **Personalized follow-up email generation** — context-aware draft emails tailored to each lead's profile
- **Human-in-the-loop approval** — no email is ever sent automatically; every draft requires explicit human approval
- **CRM integration** — bi-directional sync with HubSpot, Google Sheets, and Airtable
- **Slack notifications** — instant alerts for hot leads routed to the right channel
- **n8n webhook support** — plug into any n8n automation workflow as a trigger or action
- **Real-time dashboard** — Next.js frontend for lead management, email approval, and analytics
- **Docker containerized** — single `docker compose up` deployment for all services

---

## Architecture

```
                        +--------------------------+
                        |      LEAD SOURCES        |
                        |--------------------------|
                        | Website Forms  | Webhooks |
                        | CRM Sync       | n8n      |
                        | Google Sheets  | Airtable |
                        +----------+---------------+
                                   |
                                   v
                    +--------------+---------------+
                    |       FastAPI Backend        |
                    |------------------------------|
                    |  - Lead Intake & Validation  |
                    |  - Hybrid Scoring Engine     |
                    |  - AI Analysis (OpenAI)      |
                    |  - Email Draft Generation    |
                    |  - Activity Logging          |
                    +----+----------+--------+-----+
                         |          |        |
            +------------+    +-----+    +---+----------+
            |                 |          |
            v                 v          v
     +-------------+   +----------+   +-------------------+
     | PostgreSQL  |   |  OpenAI  |   |   Integrations    |
     |-------------|   |  API     |   |-------------------|
     | leads       |   | GPT-4o   |   | Google Sheets     |
     | activities  |   | -mini    |   | Airtable          |
     | email_drafts|   +----------+   | HubSpot           |
     | settings    |                  | Slack             |
     +-------------+                  | n8n Webhooks      |
                                       | SMTP Email        |
                                       +-------------------+

                    +--------------+---------------+
                    |    Next.js Frontend Dashboard |
                    |-------------------------------|
                    |  Lead List  | Lead Detail     |
                    |  Email Approval | Analytics   |
                    |  Settings                     |
                    +-------------------------------+
                                   |
                                   | REST API (HTTP/JSON)
                                   v
                    +--------------+---------------+
                    |       FastAPI Backend        |
                    +------------------------------+
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12, FastAPI 0.115, SQLAlchemy, Alembic, Pydantic v2 |
| **Frontend** | Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| **Database** | PostgreSQL 16 |
| **AI** | OpenAI GPT-4o-mini |
| **Task Queue** | Background tasks via FastAPI (AsyncIO) |
| **Integrations** | Google Sheets API, Airtable REST API, HubSpot API, Slack Webhooks, n8n Webhooks, SMTP |
| **Containerization** | Docker, Docker Compose |
| **Testing** | pytest, httpx |

---

## Project Structure

```
ai-lead-qualification-agent/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── leads.py          # Lead CRUD & submission endpoints
│   │   │   │   ├── emails.py         # Email draft & approval endpoints
│   │   │   │   ├── analytics.py      # Dashboard analytics endpoints
│   │   │   │   ├── settings.py       # App settings endpoints
│   │   │   │   └── webhooks.py       # Inbound webhook receivers
│   │   │   └── deps.py               # Dependency injection (DB session, etc.)
│   │   ├── core/
│   │   │   ├── config.py             # Environment config (Pydantic Settings)
│   │   │   ├── database.py           # SQLAlchemy engine & session
│   │   │   └── security.py           # Auth helpers, webhook signature validation
│   │   ├── models/
│   │   │   ├── lead.py               # Lead ORM model
│   │   │   ├── activity.py           # Activity log ORM model
│   │   │   ├── email_draft.py        # Email draft ORM model
│   │   │   └── settings.py           # App settings ORM model
│   │   ├── schemas/
│   │   │   ├── lead.py               # Lead Pydantic schemas
│   │   │   ├── email.py              # Email draft Pydantic schemas
│   │   │   └── analytics.py          # Analytics Pydantic schemas
│   │   ├── services/
│   │   │   ├── scoring.py            # Hybrid scoring engine (rules + AI)
│   │   │   ├── ai_analysis.py        # OpenAI integration & prompt management
│   │   │   ├── email_generator.py    # Personalized email draft generation
│   │   │   ├── email_sender.py       # SMTP email sending service
│   │   │   └── integrations/
│   │   │       ├── google_sheets.py  # Google Sheets sync
│   │   │       ├── airtable.py       # Airtable sync
│   │   │       ├── hubspot.py        # HubSpot CRM sync
│   │   │       ├── slack.py          # Slack notifications
│   │   │       └── n8n.py            # n8n webhook triggers
│   │   └── main.py                   # FastAPI app entry point
│   ├── alembic/                      # Database migrations
│   ├── tests/                        # pytest test suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── leads/                # Lead list & detail pages
│   │   │   ├── emails/               # Email approval pages
│   │   │   ├── analytics/            # Analytics dashboard
│   │   │   └── settings/             # Settings pages
│   │   ├── components/               # Reusable UI components
│   │   ├── lib/
│   │   │   ├── api.ts                # API client
│   │   │   └── utils.ts              # Utilities
│   │   └── types/                    # TypeScript type definitions
│   ├── Dockerfile
│   ├── package.json
│   └── next.config.ts
├── docs/
│   ├── integration-guide.md          # Integration setup instructions
│   ├── api-reference.md              # Full API reference
│   └── scoring-system.md             # Scoring system deep-dive
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- OpenAI API key

---

### Local Development

**1. Clone the repository**

```bash
git clone https://github.com/Zotriq/ai-lead-qualification-agent.git
cd ai-lead-qualification-agent
```

**2. Create your environment file**

```bash
cp .env.example .env
# Edit .env and fill in your values (see Environment Variables section below)
```

**3. Set up the backend**

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

**4. Set up the frontend**

```bash
# Open a new terminal
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

**5. Access the application**

Open `http://localhost:3000` in your browser.

---

### Docker Compose

**1. Clone the repository**

```bash
git clone https://github.com/Zotriq/ai-lead-qualification-agent.git
cd ai-lead-qualification-agent
```

**2. Create your environment file**

```bash
cp .env.example .env
# Edit .env and fill in your values
```

**3. Build and start all services**

```bash
docker compose up --build
```

**4. Access the application**

Open `http://localhost:3000` in your browser. The API is at `http://localhost:8000`.

To stop all services:

```bash
docker compose down
```

To stop and remove all data volumes:

```bash
docker compose down -v
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure the following variables:

### Core

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@localhost:5432/leads_db` |
| `SECRET_KEY` | Application secret key (generate with `openssl rand -hex 32`) | *(required)* |
| `ENVIRONMENT` | Runtime environment (`development` / `production`) | `development` |
| `DEBUG` | Enable debug logging | `false` |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:3000` |

### OpenAI

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key | *(required)* |
| `OPENAI_MODEL` | Model used for lead analysis and email generation | `gpt-4o-mini` |
| `OPENAI_MAX_TOKENS` | Maximum tokens per AI response | `1000` |

### Email (SMTP)

| Variable | Description | Default |
|---|---|---|
| `SMTP_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USERNAME` | SMTP username / email address | *(required)* |
| `SMTP_PASSWORD` | SMTP password or app password | *(required)* |
| `SMTP_FROM_EMAIL` | Sender email address | *(required)* |
| `SMTP_FROM_NAME` | Sender display name | `Sales Team` |
| `SMTP_USE_TLS` | Enable STARTTLS | `true` |

### Google Sheets

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_SHEETS_ENABLED` | Enable Google Sheets integration | `false` |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | Path to service account credentials JSON | *(required if enabled)* |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | Target spreadsheet ID | *(required if enabled)* |
| `GOOGLE_SHEETS_WORKSHEET_NAME` | Worksheet/tab name | `Leads` |

### Airtable

| Variable | Description | Default |
|---|---|---|
| `AIRTABLE_ENABLED` | Enable Airtable integration | `false` |
| `AIRTABLE_API_KEY` | Airtable personal access token | *(required if enabled)* |
| `AIRTABLE_BASE_ID` | Airtable base ID | *(required if enabled)* |
| `AIRTABLE_TABLE_NAME` | Airtable table name | `Leads` |

### HubSpot

| Variable | Description | Default |
|---|---|---|
| `HUBSPOT_ENABLED` | Enable HubSpot CRM integration | `false` |
| `HUBSPOT_API_KEY` | HubSpot private app access token | *(required if enabled)* |
| `HUBSPOT_PIPELINE_ID` | HubSpot deal pipeline ID | *(optional)* |

### Slack

| Variable | Description | Default |
|---|---|---|
| `SLACK_ENABLED` | Enable Slack notifications | `false` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | *(required if enabled)* |
| `SLACK_HOT_LEADS_CHANNEL` | Channel for hot lead alerts | `#hot-leads` |

### n8n

| Variable | Description | Default |
|---|---|---|
| `N8N_ENABLED` | Enable n8n webhook triggers | `false` |
| `N8N_WEBHOOK_URL` | n8n webhook URL to call on new leads | *(required if enabled)* |
| `N8N_WEBHOOK_SECRET` | Shared secret for n8n webhook validation | *(optional)* |

### Inbound Webhook Security

| Variable | Description | Default |
|---|---|---|
| `WEBHOOK_SECRET` | Secret token required in `X-Webhook-Secret` header | *(optional)* |

---

## API Examples

### Submit a Lead

```bash
curl -X POST http://localhost:8000/api/v1/leads \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane.smith@acme.com",
    "company": "Acme Corp",
    "title": "VP of Engineering",
    "phone": "+1-555-0100",
    "budget": 50000,
    "timeline": "Q3 2026",
    "company_size": 250,
    "industry": "Technology",
    "country": "US",
    "message": "We need to automate our sales pipeline. Looking for an enterprise solution.",
    "source": "website_form"
  }'
```

**Response:**

```json
{
  "id": "lq_01j9z4abc123",
  "status": "qualified",
  "tier": "hot",
  "score": 82,
  "ai_summary": "High-intent VP-level lead from a mid-size tech company with clear budget and near-term timeline.",
  "email_draft_id": "ed_01j9z4xyz789",
  "created_at": "2026-05-14T10:30:00Z"
}
```

---

### List Leads

```bash
curl -X GET "http://localhost:8000/api/v1/leads?tier=hot&limit=20&offset=0" \
  -H "Accept: application/json"
```

---

### Get Dashboard Summary

```bash
curl -X GET http://localhost:8000/api/v1/analytics/summary \
  -H "Accept: application/json"
```

**Response:**

```json
{
  "total_leads": 148,
  "hot": 23,
  "warm": 41,
  "cold": 55,
  "unqualified": 29,
  "emails_pending_approval": 18,
  "emails_sent_today": 5,
  "avg_score": 47.3
}
```

---

### Approve Email

```bash
curl -X POST http://localhost:8000/api/v1/emails/ed_01j9z4xyz789/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved_by": "sales@acme.com",
    "edited_subject": "Following up on your automation inquiry",
    "edited_body": "Hi Jane, ..."
  }'
```

---

## Scoring System

Every submitted lead is evaluated by a **hybrid scoring engine** that combines deterministic business rules with AI judgment.

### Business Rules Score (0-100)

The rules engine assigns points across the following signals:

| Signal | Weight | Criteria |
|---|---|---|
| **Budget** | High | Tiered by stated budget amount |
| **Timeline** | High | Immediate > 1 quarter > 1 year > unclear |
| **Company Size** | Medium | Mid-market and enterprise score higher |
| **Job Title** | High | C-suite / VP / Director score highest |
| **Industry** | Medium | Target industries score higher |
| **Country** | Medium | Primary markets score higher |
| **Intent Signals** | High | Specific language in message (pricing, demo, etc.) |
| **Spam Detection** | Negative | Generic domains, suspicious patterns reduce score |
| **Completeness** | Medium | More fields filled = higher score |

### AI Analysis Score (0-100)

OpenAI GPT-4o-mini independently evaluates the lead and returns a structured score with reasoning. The AI considers:

- Overall intent and urgency expressed in the message
- Alignment between stated need and product capabilities
- Seniority and decision-making authority implied by the title
- Budget and timeline plausibility
- Red flags (unrealistic expectations, scope mismatch, etc.)

### Final Score Calculation

```
Final Score = (AI Score × 0.60) + (Rules Score × 0.40)
```

### Classification Thresholds

| Tier | Score Range | Action |
|---|---|---|
| **Hot** | 75 – 100 | Immediate Slack alert + priority email draft |
| **Warm** | 50 – 74 | Email draft generated, standard queue |
| **Cold** | 25 – 49 | Email draft generated, low priority |
| **Unqualified** | 0 – 24 | No email generated, archived |

---

## AI Analysis

### What the AI Does

For every lead that passes spam detection, the AI analysis service sends the lead's full profile to OpenAI GPT-4o-mini with a structured system prompt. The AI returns:

1. A **numerical score** (0-100) representing lead quality
2. A concise **natural-language summary** for the sales team
3. Identified **intent signals** extracted from the message
4. A **recommended action** (call, email, nurture, disqualify)
5. **Key talking points** for the follow-up email

### System Prompt

The system prompt instructs GPT-4o-mini to act as an expert B2B sales analyst. It provides:
- Product context (what the product does, ideal customer profile)
- Evaluation criteria (budget fit, authority, need, timing)
- Required JSON response schema
- Fallback behavior guidelines

### Response Schema

```json
{
  "score": 82,
  "summary": "High-intent VP-level lead...",
  "intent_signals": ["pricing inquiry", "demo request", "specific timeline"],
  "recommended_action": "call",
  "talking_points": ["Mention enterprise tier", "Reference Q3 deadline"],
  "confidence": "high"
}
```

### Fallback Behavior

If the OpenAI API is unavailable or returns an error:
- The lead is still saved and scored using only the rules engine
- A warning activity is logged against the lead
- The AI score defaults to the rules score (no blending penalty)
- The lead is flagged for manual review in the dashboard
- No leads are ever lost due to AI service failures

---

## Human Approval Flow

**No email is ever sent automatically.** Every outbound email goes through the following approval workflow:

```
Lead Submitted
      |
      v
[SCORING & AI ANALYSIS]
      |
      v
[EMAIL DRAFT GENERATED]  <-- status: draft_generated
      |
      v
[PENDING HUMAN REVIEW]   <-- status: pending_approval
      |
    / | \
   /  |  \
  v   |   v
EDIT  |  REJECT  <-- status: rejected (no email sent)
  \   |
   \  v
    APPROVE  <-- status: approved
      |
      v
   [SEND]  <-- status: sent
```

The dashboard surfaces all drafts in `pending_approval` status. Sales team members can:
- **Read** the AI-generated draft alongside the full lead profile
- **Edit** the subject or body before approving
- **Approve** — triggers immediate sending via SMTP
- **Reject** — archives the draft with an optional rejection reason

The approval action is logged with the approver's identity and timestamp for full audit trail.

---

## Integrations

### Google Sheets

Automatically syncs new leads (and updates on re-scoring) to a designated Google Sheet. Each row contains all lead fields plus score, tier, and AI summary. Useful for teams that prefer spreadsheet-based review.

### Airtable

Pushes leads to an Airtable base with rich field types (ratings, dropdowns, long text). Supports bi-directional status sync — updating a lead's status in Airtable can optionally propagate back via webhook.

### HubSpot

Creates or updates Contact and Deal records in HubSpot. Maps lead tier to deal stage. Hot leads can be auto-assigned to a specific sales rep or pipeline stage based on configuration.

### Slack

Sends formatted Slack messages to a configurable channel whenever a **hot lead** is received. The message includes lead name, company, score, AI summary, and a direct link to the approval dashboard.

### n8n

Triggers an n8n webhook on every new qualified lead, passing the full lead payload as JSON. This allows connecting the agent to any downstream workflow — CRM sequences, calendar booking, data enrichment, and more.

### SMTP Email

All outbound emails are sent via standard SMTP. Supports Gmail, Outlook, SendGrid, Mailgun, or any SMTP relay. TLS is enabled by default. Delivery status is logged against each lead.

For detailed integration setup instructions, see [docs/integration-guide.md](docs/integration-guide.md).

---

## Dashboard

The Next.js frontend provides five primary views:

### 1. Lead List
Paginated, filterable table of all leads. Filter by tier (hot/warm/cold/unqualified), date range, source, and score range. Bulk actions: re-score, export CSV.

### 2. Lead Detail
Full lead profile with side-by-side display of: submitted data, AI analysis (score, summary, intent signals, talking points), scoring breakdown (rules vs AI), activity timeline, and linked email drafts.

### 3. Email Approval
Focused approval queue showing all drafts in `pending_approval` status. Inline editor for subject and body. One-click approve or reject with optional notes. Approved emails show delivery confirmation.

### 4. Analytics
Real-time pipeline metrics: lead volume by day/week/month, tier distribution pie chart, average score over time, source attribution breakdown, email approval rate, and top-performing lead sources.

### 5. Settings
Configure scoring thresholds, AI model parameters, SMTP settings, integration toggles, Slack channel, n8n endpoint, and webhook secret — all without redeploying.

---

## Error Handling

The system is designed with a "never lose a lead" philosophy:

- **Raw payload saved first** — the inbound lead payload is persisted to the database before any processing begins. If scoring or AI analysis fails, the raw data is never lost.
- **Activity log** — every significant event (lead received, scoring completed, AI analysis failed, email sent, approval by user) is appended to the lead's activity log with timestamp and details.
- **Integration failures are non-blocking** — if Google Sheets, HubSpot, or Slack fails, the lead is fully processed and the integration failure is logged as a warning. Failed integrations are flagged in the dashboard for retry.
- **Retry support** — failed integration syncs can be manually retried from the Lead Detail view or via API (`POST /api/v1/leads/{id}/retry-integrations`).
- **Graceful AI fallback** — OpenAI failures fall back to rules-only scoring (see AI Analysis section).
- **Structured error responses** — all API errors return consistent `{ "error": "...", "detail": "..." }` JSON with appropriate HTTP status codes.

---

## Security

- **Secrets via environment variables** — no credentials are hardcoded. All secrets are loaded from environment variables at runtime.
- **Webhook signature validation** — inbound webhooks can require a shared secret in the `X-Webhook-Secret` header. Invalid or missing secrets return `401 Unauthorized`.
- **Input sanitization** — all inbound lead fields are validated and sanitized via Pydantic schemas. SQL injection is prevented by SQLAlchemy ORM parameterized queries.
- **Rate limiting** — the submission endpoint is rate-limited by IP address to prevent abuse and spam flooding.
- **CORS** — Cross-Origin Resource Sharing is restricted to explicitly configured origins via `ALLOWED_ORIGINS`.
- **No automatic email sending** — the human approval gate ensures no unsolicited email can be sent, even in the event of a misconfiguration.
- **Basic auth for MVP** — the dashboard and API support HTTP Basic Authentication for MVP deployments. Replace with OAuth2/JWT for production multi-user use.
- **No sensitive data in logs** — email addresses and personal data are masked in structured logs.

---

## Troubleshooting

### Database connection fails on startup

Verify that `DATABASE_URL` is correct and that the PostgreSQL server is running and accepting connections. For Docker Compose setups, ensure the `db` service is healthy before the backend starts (`depends_on: db: condition: service_healthy`).

```bash
# Test the connection directly
psql $DATABASE_URL -c "SELECT 1;"
```

### OpenAI API errors

- Confirm `OPENAI_API_KEY` is set and valid.
- Check your OpenAI account for quota limits or billing issues.
- The system will fall back to rules-only scoring — check the lead's activity log for the specific error.

### CORS errors in the browser

Ensure `ALLOWED_ORIGINS` includes the exact origin of your frontend, including protocol and port (e.g., `http://localhost:3000`). Trailing slashes will cause mismatches.

### Docker networking issues

If the frontend cannot reach the backend inside Docker Compose, ensure both services are on the same Docker network and that the frontend uses the service name (`http://backend:8000`) rather than `localhost` for server-side API calls.

### Integration sync failures

Check the lead's activity log in the dashboard for the exact error message. Common causes:
- **Google Sheets**: Service account credentials JSON not mounted correctly, or the service account does not have edit access to the spreadsheet.
- **Airtable**: Incorrect `AIRTABLE_BASE_ID` or table name. Verify field names match the Airtable schema exactly.
- **HubSpot**: Expired or revoked private app token. Regenerate in HubSpot settings.
- **Slack**: Webhook URL has been revoked or the app removed from the workspace.

For additional help, see [docs/integration-guide.md](docs/integration-guide.md).

---

## Future Improvements

The following enhancements are planned for future releases:

- **Authentication & roles** — JWT-based auth with role-based access control (admin, sales rep, viewer)
- **Multi-team support** — separate lead pools, scoring configs, and email templates per team
- **Advanced CRM sync** — full bi-directional sync with Salesforce and Pipedrive
- **Calendar booking integration** — embed Calendly / Cal.com links in approved emails for hot leads
- **Lead deduplication** — detect and merge duplicate leads by email/company before scoring
- **Email tracking** — open and click tracking on sent emails to measure engagement
- **Conversion analytics** — track which leads become customers and tune scoring weights accordingly
- **Custom AI scoring profiles** — per-product or per-campaign AI system prompts
- **A/B testing for email templates** — test multiple email variants and track approval/reply rates
- **Forecasting** — predict monthly pipeline value from current lead scores and historical conversion rates

---

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository and create a feature branch from `main`.
2. Make your changes with clear, focused commits.
3. Add or update tests for any changed functionality.
4. Ensure all tests pass: `pytest backend/tests/`
5. Ensure the frontend builds without errors: `npm run build`
6. Open a pull request with a clear description of the change and the problem it solves.

Please open an issue before starting work on large features to discuss the approach.

---

## License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2026 Zohaib Tariq

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
