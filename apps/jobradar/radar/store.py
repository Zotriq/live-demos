"""Database layer. SQLite by default; set DATABASE_URL to use Postgres / Supabase."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Text,
    UniqueConstraint, create_engine, delete, func, insert, select, update,
)

from .models import Job, RunResult, Score
from .normalize import TRACKED_FIELDS

meta = MetaData()

runs = Table(
    "runs", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("mode", String(16)),
    Column("profile", String(200)),
    Column("fetched", Integer, default=0),
    Column("new", Integer, default=0),
    Column("duplicates", Integer, default=0),
    Column("updated", Integer, default=0),
    Column("closed", Integer, default=0),
    Column("scored_llm", Integer, default=0),
    Column("scored_rules", Integer, default=0),
    Column("alerts", Integer, default=0),
    Column("errors", JSON),
)

jobs = Table(
    "jobs", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("fingerprint", String(32), nullable=False, unique=True),   # the dedup key
    Column("source", String(32), nullable=False),
    Column("source_id", String(128), nullable=False),
    Column("board", String(128)),
    Column("seen_on", JSON),                                          # every source/board it appeared on
    Column("title", String(300), nullable=False),
    Column("company", String(200), nullable=False),
    Column("location", String(300)),
    Column("remote", Boolean, default=False),
    Column("department", String(200)),
    Column("employment_type", String(64)),
    Column("salary", String(120)),
    Column("url", Text),
    Column("description", Text),
    Column("posted_at", DateTime(timezone=True)),
    Column("content_hash", String(32)),
    Column("score", Integer),
    Column("rule_score", Integer),
    Column("score_reason", Text),
    Column("score_engine", String(16)),
    Column("matched_skills", JSON),
    Column("is_active", Boolean, default=True),
    Column("first_seen", DateTime(timezone=True)),
    Column("last_seen", DateTime(timezone=True)),
    Column("first_run_id", Integer),
    Column("alerted_at", DateTime(timezone=True)),
    UniqueConstraint("source", "source_id", name="uq_source_id"),
)

job_history = Table(
    "job_history", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("job_id", Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", Integer),
    Column("changed_at", DateTime(timezone=True), nullable=False),
    Column("event", String(16)),          # created | updated | closed | reopened
    Column("changes", JSON),              # {field: [old, new]}
)

alerts = Table(
    "alerts", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("job_id", Integer, ForeignKey("jobs.id", ondelete="CASCADE")),
    Column("run_id", Integer),
    Column("channel", String(80)),
    Column("kind", String(16)),           # job | digest | test
    Column("status", String(16)),         # sent | preview | failed
    Column("detail", Text),
    Column("payload", JSON),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def default_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url
    path = Path(os.getenv("JOB_RADAR_DB", Path(__file__).resolve().parent.parent / "data" / "job_radar.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


class Store:
    def __init__(self, url: Optional[str] = None):
        self.url = url or default_url()
        self.engine = create_engine(self.url, future=True, pool_pre_ping=True)
        meta.create_all(self.engine)

    @property
    def kind(self) -> str:
        return "PostgreSQL" if self.engine.dialect.name.startswith("postgres") else "SQLite"

    # ------------------------------------------------------------- runs
    def start_run(self, mode: str, profile: str) -> int:
        with self.engine.begin() as c:
            return c.execute(insert(runs).values(started_at=now(), mode=mode, profile=profile, errors=[])).inserted_primary_key[0]

    def finish_run(self, r: RunResult):
        with self.engine.begin() as c:
            c.execute(update(runs).where(runs.c.id == r.run_id).values(
                finished_at=now(), fetched=r.fetched, new=r.new, duplicates=r.duplicates,
                updated=r.updated, closed=r.closed, scored_llm=r.scored_llm,
                scored_rules=r.scored_rules, alerts=r.alerts, errors=r.errors))

    # ------------------------------------------------------------- jobs
    def upsert(self, job: Job, run_id: int) -> tuple[str, int]:
        """Returns (outcome, job_id). outcome: new | duplicate | updated | reopened."""
        ts = now()
        with self.engine.begin() as c:
            row = c.execute(select(jobs).where(
                (jobs.c.fingerprint == job.fingerprint) |
                ((jobs.c.source == job.source) & (jobs.c.source_id == job.source_id))
            )).mappings().first()

            if row is None:
                jid = c.execute(insert(jobs).values(
                    fingerprint=job.fingerprint, source=job.source, source_id=job.source_id,
                    board=job.board, seen_on=[f"{job.source}:{job.board}"], title=job.title,
                    company=job.company, location=job.location, remote=job.remote,
                    department=job.department, employment_type=job.employment_type,
                    salary=job.salary, url=job.url, description=job.description,
                    posted_at=job.posted_at, content_hash=job.content_hash, is_active=True,
                    first_seen=ts, last_seen=ts, first_run_id=run_id,
                )).inserted_primary_key[0]
                c.execute(insert(job_history).values(job_id=jid, run_id=run_id, changed_at=ts, event="created", changes={}))
                return "new", jid

            jid = row["id"]
            seen = list(row["seen_on"] or [])
            tag = f"{job.source}:{job.board}"
            if tag not in seen:
                seen.append(tag)
            values = {"last_seen": ts, "seen_on": seen}
            outcome = "duplicate"

            same_listing = row["source"] == job.source and row["source_id"] == job.source_id
            if not row["is_active"]:
                values["is_active"] = True
                c.execute(insert(job_history).values(job_id=jid, run_id=run_id, changed_at=ts, event="reopened", changes={}))
                outcome = "reopened"

            if same_listing and row["content_hash"] != job.content_hash:
                changes = {}
                for f in TRACKED_FIELDS:
                    old, new = row[f], getattr(job, f)
                    if (old or "") != (new or ""):
                        changes[f] = [_short(old), _short(new)]
                if changes:
                    values.update({f: getattr(job, f) for f in TRACKED_FIELDS})
                    values.update(content_hash=job.content_hash)
                    c.execute(insert(job_history).values(job_id=jid, run_id=run_id, changed_at=ts, event="updated", changes=changes))
                    outcome = "updated"
            c.execute(update(jobs).where(jobs.c.id == jid).values(**values))
            return outcome, jid

    def close_missing(self, source: str, board: str, seen_ids: set[str], run_id: int) -> int:
        """Jobs a source no longer lists are marked closed, not deleted (history is kept)."""
        ts = now()
        with self.engine.begin() as c:
            rows = c.execute(select(jobs.c.id, jobs.c.source_id).where(
                (jobs.c.source == source) & (jobs.c.board == board) & (jobs.c.is_active == True)  # noqa: E712
            )).all()
            gone = [r.id for r in rows if r.source_id not in seen_ids]
            for jid in gone:
                c.execute(update(jobs).where(jobs.c.id == jid).values(is_active=False))
                c.execute(insert(job_history).values(job_id=jid, run_id=run_id, changed_at=ts, event="closed", changes={}))
            return len(gone)

    def save_score(self, job_id: int, s: Score):
        with self.engine.begin() as c:
            c.execute(update(jobs).where(jobs.c.id == job_id).values(
                score=s.score, rule_score=s.rule_score, score_reason=s.reason,
                score_engine=s.engine, matched_skills=s.matched_skills))

    def mark_alerted(self, job_id: int):
        with self.engine.begin() as c:
            c.execute(update(jobs).where(jobs.c.id == job_id).values(alerted_at=now()))

    def log_alert(self, job_id, run_id, channel, kind, status, detail, payload):
        with self.engine.begin() as c:
            c.execute(insert(alerts).values(job_id=job_id, run_id=run_id, channel=channel, kind=kind,
                                            status=status, detail=detail, payload=payload, created_at=now()))

    # ------------------------------------------------------------- reads
    def job(self, job_id: int) -> Optional[dict]:
        with self.engine.connect() as c:
            r = c.execute(select(jobs).where(jobs.c.id == job_id)).mappings().first()
            return dict(r) if r else None

    def all_jobs(self) -> list[dict]:
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(jobs).order_by(jobs.c.score.desc().nulls_last(), jobs.c.first_seen.desc())).mappings()]

    def jobs_by_ids(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        with self.engine.connect() as c:
            rows = [dict(r) for r in c.execute(select(jobs).where(jobs.c.id.in_(ids))).mappings()]
        return sorted(rows, key=lambda r: -(r["score"] or 0))

    def history(self, job_id: int) -> list[dict]:
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(job_history).where(job_history.c.job_id == job_id).order_by(job_history.c.changed_at.desc(), job_history.c.id.desc())).mappings()]

    def runs(self, limit: int = 50) -> list[dict]:
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(runs).order_by(runs.c.id.desc()).limit(limit)).mappings()]

    def alerts(self, limit: int = 100) -> list[dict]:
        with self.engine.connect() as c:
            q = (select(alerts, jobs.c.title, jobs.c.company, jobs.c.score)
                 .select_from(alerts.outerjoin(jobs, alerts.c.job_id == jobs.c.id))
                 .order_by(alerts.c.id.desc()).limit(limit))
            return [dict(r) for r in c.execute(q).mappings()]

    def stats(self) -> dict:
        with self.engine.connect() as c:
            total = c.execute(select(func.count()).select_from(jobs)).scalar() or 0
            active = c.execute(select(func.count()).select_from(jobs).where(jobs.c.is_active == True)).scalar() or 0  # noqa: E712
            strong = c.execute(select(func.count()).select_from(jobs).where(jobs.c.score >= 70)).scalar() or 0
            sent = c.execute(select(func.count()).select_from(alerts).where(alerts.c.kind == "job")).scalar() or 0
            n_runs = c.execute(select(func.count()).select_from(runs)).scalar() or 0
            last = c.execute(select(runs.c.finished_at).order_by(runs.c.id.desc()).limit(1)).scalar()
        return {"total": total, "active": active, "strong": strong, "alerts": sent, "runs": n_runs, "last_run": last}

    def reset(self):
        with self.engine.begin() as c:
            for t in (alerts, job_history, jobs, runs):
                c.execute(delete(t))


def _short(v):
    if v is None:
        return None
    s = str(v)
    return s if len(s) <= 160 else s[:157] + "..."


def to_json(v):
    return json.dumps(v, default=str)
