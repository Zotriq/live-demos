"""Command line: run once, run on a schedule, or print a summary report."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from .pipeline import run_pipeline

REPORT_SQL = {
    "Last runs": """
        SELECT id, status, fx_source, extracted, loaded, rejected, started_at
        FROM etl_runs ORDER BY id DESC LIMIT 5""",
    "Revenue by month (USD)": """
        SELECT substr(CAST(order_date AS TEXT), 1, 7) AS month, COUNT(*) AS orders, SUM(amount_usd) AS revenue_usd
        FROM orders WHERE status <> 'refunded' GROUP BY 1 ORDER BY 1""",
    "Top customers (USD)": """
        SELECT c.name, c.country, SUM(o.amount_usd) AS spent_usd
        FROM orders o JOIN customers c ON c.email = o.customer_email
        WHERE o.status <> 'refunded' GROUP BY c.name, c.country ORDER BY spent_usd DESC LIMIT 5""",
    "Rejected rows (latest run)": """
        SELECT source, source_row, order_ref, reason FROM rejected_records
        WHERE run_id = (SELECT MAX(id) FROM etl_runs) ORDER BY source, source_row""",
}


def _settings():
    load_dotenv()
    return (
        create_engine(os.getenv("DATABASE_URL", "sqlite:///etl.db")),
        Path(os.getenv("DATA_DIR", "data")),
        os.getenv("FX_API_URL", "https://open.er-api.com/v6/latest/USD"),
    )


def _print_table(title: str, rows, keys) -> None:
    print(f"\n== {title}")
    if not rows:
        print("  (none)")
        return
    widths = [max(len(str(k)), *(len(str(r[i])) for r in rows)) for i, k in enumerate(keys)]
    print("  " + "  ".join(str(k).ljust(w) for k, w in zip(keys, widths)))
    for r in rows:
        print("  " + "  ".join(str(v).ljust(w) for v, w in zip(r, widths)))


def cmd_run(_args) -> None:
    engine, data_dir, fx_url = _settings()
    r = run_pipeline(engine, data_dir, fx_url)
    print(f"Run {r.run_id}: {r.status} | extracted {r.extracted} | loaded {r.loaded} | rejected {r.rejected} | FX: {r.fx_source}")


def cmd_report(_args) -> None:
    engine, *_ = _settings()
    with engine.connect() as conn:
        for title, sql in REPORT_SQL.items():
            res = conn.execute(text(sql))
            _print_table(title, res.fetchall(), list(res.keys()))


def cmd_schedule(args) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler()
    scheduler.add_job(cmd_run, "interval", minutes=args.every, args=[args])
    print(f"Running every {args.every} min. Ctrl+C to stop.")
    cmd_run(args)
    scheduler.start()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="etl", description="Multi-source orders ETL")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="run the pipeline once").set_defaults(func=cmd_run)
    sub.add_parser("report", help="print revenue, top customers and rejected rows").set_defaults(func=cmd_report)
    sched = sub.add_parser("schedule", help="run on a fixed interval")
    sched.add_argument("--every", type=int, default=60, help="minutes between runs")
    sched.set_defaults(func=cmd_schedule)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
