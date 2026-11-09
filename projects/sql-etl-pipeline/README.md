# SQL ETL Pipeline

![tests](https://github.com/Zotriq/sql-etl-pipeline/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)

A production-style ETL pipeline that pulls sales from **two systems that don't agree on anything**, plus a live
exchange-rate API, then cleans, validates and loads them into **one trustworthy PostgreSQL database**.

It's built the way a client's real data looks: different column names, comma vs. semicolon files,
`$1,249.50` vs. `18.990,00`, three date formats, duplicate rows, missing emails and negative totals.

## What it does

```
 webstore_orders.csv ─┐   (comma, US amounts, mixed date formats)
                      ├─► EXTRACT ─► TRANSFORM ─────────────► LOAD (PostgreSQL)
 pos_sales.csv ───────┘   map to     • parse amounts/dates      • customers   (upsert, merged across sources)
   (semicolon, EU amounts) common    • normalize email/country  • orders      (upsert by order_id)
                           fields    • convert to USD           • rejected_records (with reason)
 Exchange-rate API ──────────────►   • validate with Pydantic   • etl_runs    (audit log of every run)
   (retry + backoff, file fallback)  • de-duplicate
```

**Built for production, not just a demo:**

- **Idempotent.** Re-running never creates duplicates. Orders and customers are upserted, and changes in the source (e.g. an order becoming `refunded`) are applied.
- **Nothing is silently dropped.** Every bad row is stored in `rejected_records` with the exact reason, so the source data can be fixed.
- **Atomic loads.** Orders and rejections commit together or not at all.
- **Resilient API calls.** Exchange rates retry with exponential backoff, then fall back to the last known rates file.
- **Audit trail.** Every run is logged in `etl_runs` with counts, FX source, status and error message.
- **Scheduling.** Run once, or on an interval with APScheduler (or cron / Docker).
- **Tested on PostgreSQL and SQLite.** 35 tests, run by GitHub Actions on every push.

## Real output

Running against the sample data in [`data/`](data):

```text
$ etl run
Run 1: success | extracted 12 | loaded 6 | rejected 5 | FX: fallback

$ etl report
== Top customers (USD)
  name         country         spent_usd
  Ayesha Khan  Pakistan        1317.32      <- merged from the web store AND the POS
  Emma Brown   United States   310.00
  Liam Smith   United Kingdom  112.66       <- converted from GBP
  Bilal Ahmed  Pakistan        16.07        <- converted from PKR

== Rejected rows (latest run)
  source    source_row  order_ref  reason
  pos       4           P-79       order date is missing
  pos       5           P-80       email: value is not a valid email address
  webstore  6           W-1004     email: value is not a valid email address
  webstore  7           W-1005     invalid date '2026-13-40'
  webstore  8           W-1006     amount: Input should be greater than or equal to 0
```

This run used the fallback rates file (`FX: fallback`). With internet access the pipeline uses live rates (`FX: api`), so the USD figures change slightly day to day.

## Quick start

### With Docker

```bash
git clone https://github.com/Zotriq/sql-etl-pipeline.git
cd sql-etl-pipeline
docker compose up --build        # Postgres + the pipeline running every 60 minutes
```

### Locally

```bash
pip install -e .
cp .env.example .env              # point DATABASE_URL at your Postgres (or use sqlite:///etl.db)
etl run                           # run once
etl report                        # revenue by month, top customers, rejected rows
etl schedule --every 30           # run every 30 minutes
```

Optional BI views (`monthly_revenue`, `customer_lifetime_value`, `data_quality`) for Metabase, Power BI or
Looker Studio:

```bash
psql "$DATABASE_URL" -f sql/reporting_views.sql
```

## Database tables

| Table | Contents |
|---|---|
| `customers` | One row per email across all sources: name, country, first order date |
| `orders` | Clean orders with original amount and currency, plus `amount_usd` |
| `rejected_records` | Every row that failed validation, with source, row number and reason |
| `etl_runs` | Audit log: start/finish time, status, row counts, FX source, error |

## Cleaning rules

| Problem in source | Rule |
|---|---|
| `$1,249.50`, `18.990,00`, `999,00` | Detects the decimal separator and parses all of them correctly |
| `2026-04-01`, `04/18/2026`, `12.05.2026` | Accepts ISO, US and European dates; impossible dates are rejected |
| ` Ayesha@Example.com ` | Trimmed and lower-cased; invalid emails rejected |
| `usa`, `US`, `PK`, `United Kingdom` | Normalized to one country name |
| `Paid`, `usd` | Status and currency normalized |
| Negative totals, unknown currency | Rejected with a reason |
| Exact duplicate rows | Dropped |
| Same order ID with different values | Rejected as a conflicting duplicate |

## Adding a new source

1. Add a reader in `etl/extract.py` that maps its columns to `RawOrder`.
2. Add it to the list in `etl/pipeline.py`.

All the cleaning, validation, deduplication and loading rules then apply automatically.

## Tests

```bash
pip install -e ".[dev]"
pytest                                                                       # SQLite
PG_TEST_URL=postgresql+psycopg://postgres@localhost:5432/postgres pytest     # + PostgreSQL
```

Covers amount/date parsing, every rejection rule, deduplication, API retry and fallback (mocked HTTP),
idempotent re-runs, source updates and failed-run logging.

## Project structure

```
etl/
  extract.py     CSV readers + exchange-rate API client (retry, backoff, fallback)
  transform.py   parsing, normalization, Pydantic validation, USD conversion, dedup
  load.py        table definitions and idempotent upserts (PostgreSQL / SQLite)
  pipeline.py    one run: extract -> transform -> load, recorded in etl_runs
  cli.py         etl run | report | schedule
sql/             reporting views for BI tools
data/            sample source files
tests/           pytest suite
```

## License

MIT © Zohaib Tariq
