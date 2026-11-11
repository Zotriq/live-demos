# Job Radar

An AI job discovery agent: it pulls new postings from public job APIs, removes duplicates, scores each job for relevance with rules and an LLM, stores everything with change history, and posts the strong matches to Slack.

Built as the foundation (Milestone 1) of a six-agent recruitment automation platform: Discovery → Matching → Recruiter Research → Application Assistant → Reporting → Notifications, all sharing one database.

## What it does

| Step | How |
|---|---|
| Discover | Greenhouse, Lever and Ashby public job board APIs (company career pages) and the Remotive API. Configurable companies and searches. Boards are fetched in parallel; a failing board is logged and skipped. |
| Normalise | Every posting becomes one shape: title, company, location, remote, salary, type, department, link, description, date. |
| Deduplicate | Fingerprint = company + role + primary location. Same fingerprint = same real job, even when it appears on two sources. Unique keys in the database make duplicates impossible. |
| Track changes | A content hash per posting. Changes (salary, title, location, text) are saved to `job_history`. Jobs no longer listed are marked closed, never deleted. |
| Score | Free rules (title, skills, location, seniority, exclusions) filter clear misses. Only promising jobs go to the LLM, which returns a 0-100 score and a one-line reason. |
| Alert | Jobs at or above the threshold are posted to Slack once, as Block Kit cards. Each run also posts a summary. |
| Report | Streamlit dashboard: run console, jobs database with filters and CSV/Excel export, Slack feed, run history, architecture. |

## Run it on a Mac

```bash
git clone https://github.com/Zotriq/live-demos && cd live-demos/apps/jobradar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in the keys below (all optional)
streamlit run streamlit_app.py
```

The app opens at http://localhost:8501. In `profiles/default.yaml`, set `public_demo: false` for your own use (unlimited live runs, saved profile edits).

### Keys (optional, but needed for the full demo)

- **AI scoring:** create a free key at https://console.groq.com, put it in `.env` as `GROQ_API_KEY=...`. Default model `openai/gpt-oss-20b`. An `OPENAI_API_KEY` also works.
- **Slack:** in your Slack workspace create an app at https://api.slack.com/apps → *Incoming Webhooks* → turn on → *Add New Webhook to Workspace* → pick `#new-jobs`. Paste the URL as `SLACK_WEBHOOK_URL=...`.
- **Postgres / Supabase (optional):** set `DATABASE_URL` to the connection string. Tables are created automatically; `sql/schema.sql` has the same schema for review. Without it, a local SQLite file is used.

Without keys the app still runs: rule scoring only, and Slack messages are shown as previews.

## Two data modes (sidebar)

- **Live sources:** calls the real APIs with the companies and searches in the search profile.
- **Recorded sample:** replays saved API responses (real formats, fictional companies). Works offline. *Day 1* is a first crawl; *Day 2* adds 4 new jobs, changes 1 salary and closes 2 postings, so you can show new / changed / closed.

## Command line (what a scheduler runs)

```bash
python cli.py run                  # live sources
python cli.py run --sample day1    # recorded sample
python cli.py stats
python cli.py reset
```

Schedule it with cron, GCP Cloud Run Jobs + Cloud Scheduler, or AWS ECS + EventBridge.

## Tests

```bash
pip install pytest && python -m pytest -q
```

Covers: second run adds nothing, cross-source dedup, change and closed detection, alert threshold, Greenhouse double-encoded HTML, rule scoring, LLM only for promising jobs, Slack payload and send, a failing board not stopping the run.

## Project layout

```
streamlit_app.py      Streamlit entry (navigation)
views/                run, jobs, slack, history, architecture, settings pages
radar/sources.py      source API clients + parsers (compliant feeds only)
radar/normalize.py    cleaning, fingerprint, change hash, salary detection
radar/store.py        database (SQLite or Postgres via SQLAlchemy)
radar/scoring.py      rule scorer + LLM scorer (any OpenAI-compatible API)
radar/notify.py       Slack Block Kit messages + webhook sender
radar/pipeline.py     the discovery run: fetch → dedup → score → alert → summary
profiles/default.yaml search profile (titles, skills, locations, sources, threshold)
sample_data/          recorded API responses for offline demos and tests
sql/schema.sql        Postgres / Supabase schema
cli.py                command-line runner
```

## Source notes

- Greenhouse, Lever and Ashby publish these job board APIs so that job listings can be shown elsewhere; no key needed. A handle is the last part of a careers URL (boards.greenhouse.io/**gitlab**).
- Remotive asks for at most about 4 API calls a day and requires crediting Remotive with a link back; alerts include that credit.
- LinkedIn and Indeed have no open job search API. For those, use a licensed aggregator rather than scraping.
