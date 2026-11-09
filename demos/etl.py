import tempfile
import uuid
from pathlib import Path

import pandas as pd
import psycopg
import streamlit as st
from sqlalchemy import create_engine, text

from lib import pg, ui

repo = ui.project_path("sql-etl-pipeline")
from etl.cli import REPORT_SQL  # noqa: E402
from etl.pipeline import run_pipeline  # noqa: E402

FX_URL = "https://open.er-api.com/v6/latest/USD"

ui.header(
    "SQL ETL Pipeline",
    "Two messy sales exports (an online store CSV and a shop till CSV with European number and date formats) "
    "are cleaned, validated, converted to US dollars with live exchange rates, de-duplicated and loaded into "
    "PostgreSQL. Bad rows are never silently dropped: each one is stored with the reason.",
    "sql-etl-pipeline",
    flow=["2 CSV exports", "Validate & clean", "Live FX → USD", "Upsert to Postgres", "Rejected rows logged"],
    note="Edit the input below (add a broken row, change a currency) and run the pipeline again. "
         "Each visitor gets their own private database.",
)

# One private database per browser session
if "etl_db" not in st.session_state:
    name = "etl_" + uuid.uuid4().hex[:10]
    with psycopg.connect(pg.full(), autocommit=True) as conn:
        conn.execute(f"CREATE DATABASE {name}")
    st.session_state.etl_db = name
    st.session_state.etl_dir = tempfile.mkdtemp(prefix="etl-")
host = pg.full().split("host=")[1].split()[0]
engine = create_engine(f"postgresql+psycopg://postgres@/{st.session_state.etl_db}?host={host}")
work = Path(st.session_state.etl_dir)

web = pd.read_csv(repo / "data" / "webstore_orders.csv", dtype=str, keep_default_na=False)
pos = pd.read_csv(repo / "data" / "pos_sales.csv", dtype=str, sep=";", keep_default_na=False)

st.subheader("1 · Raw input")
st.markdown("**Online store export** (`webstore_orders.csv`): mixed date formats, `$1,249.50` amounts, a duplicate row, bad emails.")
web_edit = st.data_editor(web, num_rows="dynamic", width="stretch", key="web")
st.markdown("**Shop till export** (`pos_sales.csv`): semicolons, `18.990,00` amounts, `12.05.2026` dates, a missing date.")
pos_edit = st.data_editor(pos, num_rows="dynamic", width="stretch", key="pos")

if st.button("Run the ETL pipeline", type="primary"):
    web_edit.to_csv(work / "webstore_orders.csv", index=False)
    pos_edit.to_csv(work / "pos_sales.csv", index=False, sep=";")
    (work / "fallback_rates.json").write_text((repo / "data" / "fallback_rates.json").read_text())
    with st.spinner("Extracting, fetching exchange rates, transforming, loading…"):
        try:
            st.session_state.etl_last = run_pipeline(engine, work, FX_URL)
        except Exception as exc:
            st.error(f"Run failed (recorded in etl_runs): {exc}")

result = st.session_state.get("etl_last")
if result:
    st.subheader("2 · Result")
    a, b, c, d = st.columns(4)
    a.metric("Rows read", result.extracted)
    b.metric("Loaded / updated", result.loaded)
    c.metric("Rejected", result.rejected)
    d.metric("Exchange rates", "live API" if result.fx_source == "api" else "saved backup")
    st.caption("Run it twice: the order count in PostgreSQL stays the same, because loading is an upsert keyed on the order ID.")

    with engine.connect() as conn:
        tabs = st.tabs(["Clean orders", *REPORT_SQL.keys()])
        with tabs[0]:
            st.dataframe(pd.read_sql(text(
                "SELECT order_id, source, customer_email, order_date, status, amount, currency, amount_usd "
                "FROM orders ORDER BY order_date"), conn), width="stretch", hide_index=True)
        for tab, sql in zip(tabs[1:], REPORT_SQL.values()):
            with tab:
                st.dataframe(pd.read_sql(text(sql), conn), width="stretch", hide_index=True)
ui.footer()
