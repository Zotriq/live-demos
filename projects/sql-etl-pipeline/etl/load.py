"""Load: idempotent upserts into PostgreSQL (SQLite also works for local runs and tests)."""

from __future__ import annotations

import datetime as dt
from typing import Iterable

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    func,
    select,
)
from sqlalchemy.dialects import postgresql, sqlite

from .transform import CleanOrder, Rejection

metadata = MetaData()

customers = Table(
    "customers",
    metadata,
    Column("email", String(320), primary_key=True),
    Column("name", Text, nullable=False),
    Column("country", Text, nullable=False),
    Column("first_order_date", Date, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

orders = Table(
    "orders",
    metadata,
    Column("order_id", String(64), primary_key=True),
    Column("source", String(32), nullable=False),
    Column("customer_email", String(320), ForeignKey("customers.email"), nullable=False),
    Column("order_date", Date, nullable=False),
    Column("status", String(16), nullable=False),
    Column("amount", Numeric(14, 2), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("amount_usd", Numeric(14, 2), nullable=False),
    Column("loaded_run_id", Integer, ForeignKey("etl_runs.id"), nullable=False),
)

rejected_records = Table(
    "rejected_records",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", Integer, ForeignKey("etl_runs.id"), nullable=False),
    Column("source", String(32), nullable=False),
    Column("source_row", Integer, nullable=False),
    Column("order_ref", Text),
    Column("reason", Text, nullable=False),
)

etl_runs = Table(
    "etl_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", String(16), nullable=False),
    Column("fx_source", String(16)),
    Column("extracted", Integer, default=0),
    Column("loaded", Integer, default=0),
    Column("rejected", Integer, default=0),
    Column("error", Text),
)


def _insert(engine: Engine, table: Table):
    dialect = postgresql if engine.dialect.name == "postgresql" else sqlite
    return dialect.insert(table)


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def create_schema(engine: Engine) -> None:
    metadata.create_all(engine)


def upsert_orders(conn, engine: Engine, cleaned: Iterable[CleanOrder], run_id: int) -> int:
    cleaned = list(cleaned)
    if not cleaned:
        return 0

    # One customer row per email: earliest order date, latest name/country seen.
    by_email: dict[str, dict] = {}
    for o in sorted(cleaned, key=lambda o: o.order_date):
        entry = by_email.setdefault(o.email, {"email": o.email, "first_order_date": o.order_date})
        entry.update(name=o.customer_name, country=o.country, updated_at=now())

    stmt = _insert(engine, customers).values(list(by_email.values()))
    stmt = stmt.on_conflict_do_update(
        index_elements=[customers.c.email],
        set_={
            "name": stmt.excluded.name,
            "country": stmt.excluded.country,
            "updated_at": stmt.excluded.updated_at,
            "first_order_date": func.least(customers.c.first_order_date, stmt.excluded.first_order_date)
            if engine.dialect.name == "postgresql"
            else func.min(customers.c.first_order_date, stmt.excluded.first_order_date),
        },
    )
    conn.execute(stmt)

    rows = [
        {
            "order_id": o.order_id,
            "source": o.source,
            "customer_email": o.email,
            "order_date": o.order_date,
            "status": o.status,
            "amount": o.amount,
            "currency": o.currency,
            "amount_usd": o.amount_usd,
            "loaded_run_id": run_id,
        }
        for o in cleaned
    ]
    stmt = _insert(engine, orders).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[orders.c.order_id],
        set_={c: stmt.excluded[c] for c in ("status", "amount", "currency", "amount_usd", "order_date", "loaded_run_id")},
    )
    conn.execute(stmt)
    return len(rows)


def save_rejections(conn, rejections: Iterable[Rejection], run_id: int) -> int:
    rows = [
        {"run_id": run_id, "source": r.source, "source_row": r.source_row, "order_ref": r.order_ref, "reason": r.reason}
        for r in rejections
    ]
    if rows:
        conn.execute(rejected_records.insert(), rows)
    return len(rows)


def table_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            t.name: conn.execute(select(func.count()).select_from(t)).scalar_one()
            for t in (customers, orders, rejected_records, etl_runs)
        }
