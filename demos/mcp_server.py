import json

import pandas as pd
import psycopg
import streamlit as st

from lib import llm, pg, ui

repo = ui.project_path("postgres-mcp-server")
from pg_mcp.database import Database  # noqa: E402
from pg_mcp.nl2sql import OpenAIChatClient, generate_sql  # noqa: E402
from pg_mcp.sql_guard import UnsafeQueryError  # noqa: E402

EXTRA_DATA = """
SELECT setseed(0.42);
INSERT INTO public.customers (name, email, country, created_at)
SELECT 'Customer ' || g, 'customer' || g || '@example.com',
       (ARRAY['Pakistan','UK','Italy','United States','Germany','UAE','Canada'])[1 + floor(random() * 7)::int],
       date '2025-01-01' + floor(random() * 640)::int
FROM generate_series(1, 300) g;
INSERT INTO public.products (name, category, price) VALUES
  ('Wireless Mouse','Accessories',29.99), ('Laptop Stand','Accessories',45.00), ('Webcam 1080p','Accessories',59.00),
  ('34" Ultrawide Monitor','Displays',499.00), ('Portable Monitor','Displays',179.00), ('Noise-cancelling Headphones','Audio',199.00),
  ('Bluetooth Speaker','Audio',79.00), ('USB Microphone','Audio',119.00), ('Standing Desk','Furniture',389.00), ('Ergonomic Chair','Furniture',329.00);
INSERT INTO public.orders (customer_id, status, ordered_at)
SELECT 1 + floor(random() * 303)::int,
       (ARRAY['paid','paid','shipped','shipped','pending','refunded'])[1 + floor(random() * 6)::int],
       date '2025-01-01' + floor(random() * 680)::int
FROM generate_series(1, 2500);
INSERT INTO public.order_items
SELECT o.id, p.id, 1 + floor(random() * 3)::int
FROM public.orders o
CROSS JOIN LATERAL (SELECT id FROM public.products ORDER BY random() + o.id * 0 LIMIT 1 + floor(random() * 3)::int) p
WHERE o.id > 4
ON CONFLICT DO NOTHING;
ANALYZE;
"""

QUESTIONS = [
    "Which 5 countries brought in the most revenue from paid or shipped orders?",
    "What is the monthly revenue for 2026 so far?",
    "Which product category sells the most units?",
    "Who are the top 5 customers by total spend, and where are they from?",
    "What share of orders were refunded each quarter?",
]
ATTACKS = {
    "Delete everything": "DELETE FROM orders",
    "Drop a table": "DROP TABLE customers",
    "Hide a write in a CTE": "WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d",
    "Stack a second statement": "SELECT 1; DROP TABLE orders",
    "Read server files": "SELECT pg_read_file('/etc/passwd')",
    "Hang the server": "SELECT pg_sleep(60)",
    "Turn off the timeout": "SELECT set_config('statement_timeout', '0', false)",
    "Lock rows": "SELECT * FROM orders FOR UPDATE",
    "A normal query (allowed)": "SELECT country, count(*) AS customers FROM customers GROUP BY country ORDER BY 2 DESC",
}


@st.cache_resource(show_spinner="Creating the demo shop database…")
def shop() -> Database:
    base = pg.full()
    with psycopg.connect(base, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = 'shop'").fetchone():
            conn.execute("CREATE DATABASE shop")
    url = base.replace("dbname=postgres", "dbname=shop")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute((repo / "examples" / "shop_schema.sql").read_text())
        conn.execute(EXTRA_DATA)
    host = base.split("host=")[1].split()[0]
    return Database(f"postgresql://postgres@/shop?host={host}", max_rows=200, statement_timeout_ms=5000)


def show_rows(result: dict) -> None:
    rows = result.get("rows", [])
    st.caption(f"{result.get('row_count', len(rows))} rows" + (" (capped)" if result.get("truncated") else ""))
    st.dataframe(pd.DataFrame(rows, columns=result.get("columns")), width="stretch", hide_index=True)


ui.header(
    "Postgres MCP Server",
    "An MCP server that lets AI assistants like Claude or Cursor query a PostgreSQL database in plain English. "
    "This page calls the server's own functions directly: the AI writes SQL from the live schema, a guard checks "
    "it, and it runs in a read-only session with a timeout and a row cap.",
    "postgres-mcp-server",
    flow=["Plain-English question", "Live schema → LLM", "SQL safety guard", "Read-only execution", "Rows back"],
)
db = shop()

ask_tab, attack_tab, schema_tab, setup_tab = st.tabs(["Ask in plain English", "Try to break it", "Schema", "Use it in Claude"])

with ask_tab:
    pick = st.pills("Example questions", QUESTIONS, key="mcp_q")
    question = st.text_input("Your question about the shop database", value=pick or "")
    if st.button("Ask", type="primary", key="mcp_ask") and question.strip():
        client = OpenAIChatClient(llm.require_key(), llm.SMART, llm.GROQ_BASE_URL)
        try:
            with st.spinner("Writing SQL from the live schema…"):
                sql = generate_sql(question, db.schema_overview(), client, max_rows=200)
            st.markdown("**SQL the AI wrote (after passing the safety guard):**")
            st.code(sql, language="sql")
            show_rows(db.run_query(sql))
        except UnsafeQueryError as exc:
            st.warning(f"The guard rejected the AI's SQL twice, so nothing ran: {exc}")
        except Exception as exc:
            llm.friendly_error(exc)

with attack_tab:
    st.markdown("This is what the `run_query` tool does with whatever SQL an AI (or a prompt injection) sends it. "
                "Pick an attack or write your own.")
    pick = st.selectbox("Attack", list(ATTACKS), key="mcp_attack")
    sql = st.text_area("SQL", value=ATTACKS[pick], height=90, key=f"mcp_sql_{pick}")
    if st.button("Run through the guard", type="primary"):
        try:
            result = db.run_query(sql)
            st.success("Allowed: it's a single read-only query.")
            show_rows(result)
        except UnsafeQueryError as exc:
            st.error(f"Blocked before reaching the database: {exc}")
        except Exception as exc:
            st.error(f"Stopped by the database's read-only session: {exc}")

with schema_tab:
    for table in db.list_tables("public"):
        name = f"{table['table_schema']}.{table['table_name']}"
        label = f"{name}  ·  ~{table['approx_rows']:,} rows" + (f"  ·  {table['comment']}" if table.get("comment") else "")
        with st.expander(label):
            st.json(db.describe_table(name), expanded=True)

with setup_tab:
    st.markdown("Add the server to Claude Desktop with this config, then ask Claude about your own database:")
    st.code(json.dumps(json.loads((repo / "examples" / "claude_desktop_config.json").read_text()), indent=2), language="json")
ui.footer()
