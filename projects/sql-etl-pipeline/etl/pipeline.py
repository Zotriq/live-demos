"""Orchestrates one ETL run and records it in the etl_runs table."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import Engine, update

from . import load
from .extract import fetch_fx_rates, read_pos_csv, read_webstore_csv
from .transform import transform

log = logging.getLogger("etl")


@dataclass
class RunResult:
    run_id: int
    status: str
    extracted: int
    loaded: int
    rejected: int
    fx_source: str | None
    error: str | None = None


def run_pipeline(
    engine: Engine,
    data_dir: Path,
    fx_url: str,
    *,
    http_client: httpx.Client | None = None,
) -> RunResult:
    load.create_schema(engine)
    with engine.begin() as conn:
        run_id = conn.execute(
            load.etl_runs.insert().values(started_at=load.now(), status="running")
        ).inserted_primary_key[0]

    result = RunResult(run_id, "failed", 0, 0, 0, None)
    try:
        raw = read_webstore_csv(data_dir / "webstore_orders.csv") + read_pos_csv(data_dir / "pos_sales.csv")
        result.extracted = len(raw)
        log.info("run %s: extracted %s raw rows", run_id, len(raw))

        rates, result.fx_source = fetch_fx_rates(
            fx_url, fallback_file=data_dir / "fallback_rates.json", client=http_client
        )
        log.info("run %s: FX rates from %s", run_id, result.fx_source)

        cleaned, rejected = transform(raw, rates)

        # Data and rejections commit together, or not at all.
        with engine.begin() as conn:
            result.loaded = load.upsert_orders(conn, engine, cleaned, run_id)
            result.rejected = load.save_rejections(conn, rejected, run_id)
        result.status = "success"
        log.info("run %s: loaded %s, rejected %s", run_id, result.loaded, result.rejected)
    except Exception as exc:  # recorded on the run row, then re-raised
        result.error = f"{type(exc).__name__}: {exc}"
        log.exception("run %s failed", run_id)
        raise
    finally:
        with engine.begin() as conn:
            conn.execute(
                update(load.etl_runs)
                .where(load.etl_runs.c.id == run_id)
                .values(
                    finished_at=load.now(),
                    status=result.status,
                    fx_source=result.fx_source,
                    extracted=result.extracted,
                    loaded=result.loaded,
                    rejected=result.rejected,
                    error=result.error,
                )
            )
    return result
