import sys
import threading
import time

import psycopg
import streamlit as st

from lib import pg, ui

repo = ui.project_path("postgres-performance-tuning")
sys.path.insert(0, str(repo / "bench"))
from cases import CASES  # noqa: E402
from run import run_case  # noqa: E402

SCALE = {"customers": 200_000, "orders": 600_000, "products_big": 300_000}
LOCK = threading.Lock()


@st.cache_resource(show_spinner="Building a demo shop database (200k customers, 600k orders, 300k products)… about 30 seconds, once.")
def database() -> tuple[str, float, dict]:
    conninfo = pg.full()
    start = time.time()
    seed = (repo / "sql" / "02_seed.sql").read_text()
    for name, value in SCALE.items():
        seed = seed.replace(f":{name}", str(value))
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute((repo / "sql" / "01_schema.sql").read_text())
        conn.execute(seed)
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for t in ("customers", "orders", "order_items", "products_big")}
    return conninfo, time.time() - start, counts


ui.header(
    "PostgreSQL Performance Tuning",
    "Six slow queries from a real-world style e-commerce app. Pick one and run it: the demo times the "
    "slow version on a live PostgreSQL database, applies the fix, and times it again.",
    "postgres-performance-tuning",
    flow=["Slow query", "EXPLAIN ANALYZE", "Index or rewrite", "Measure again", "Check same result"],
)

conninfo, seconds, counts = database()
st.caption(
    f"Live PostgreSQL 18 database running inside this app: {counts['customers']:,} customers, "
    f"{counts['orders']:,} orders, {counts['order_items']:,} order items, {counts['products_big']:,} catalogue products."
)

titles = {c.title: c for c in CASES}
case = titles[st.selectbox("Choose a slow query", list(titles))]

left, right = st.columns([3, 2])
with left:
    st.markdown(f"**Scenario:** {case.scenario}")
    st.code(case.before.replace("%(", ":").replace(")s", ""), language="sql")
with right:
    st.markdown(f"**Why it's slow:** {case.why.replace('all 2 million', 'all the').replace('2 million', 'all the')}")
    st.markdown(f"**The fix:** {case.technique}")

if st.button("Run before → fix → after", type="primary"):
    with st.spinner("Undoing the fix, timing the slow query, applying the fix, timing again…"):
        with LOCK, psycopg.connect(conninfo, autocommit=True) as conn:
            result = run_case(conn, case, runs=5)
    st.session_state["tuning_result"] = (case.key, result)

if st.session_state.get("tuning_result", (None,))[0] == case.key:
    r = st.session_state["tuning_result"][1]
    a, b, c = st.columns(3)
    a.metric("Before", f"{r['before_ms']:.2f} ms")
    b.metric("After", f"{r['after_ms']:.2f} ms")
    c.metric("Speed-up", f"{r['speedup']:.0f}x")
    bp, ap = r["before_plan"], r["after_plan"]
    st.markdown(
        f"- **Rows the database had to read:** {bp['rows_scanned']:,} → {ap['rows_scanned']:,}\n"
        f"- **Plan before:** {', '.join(bp['node_types'])}\n"
        f"- **Plan after:** {', '.join(ap['node_types'])}" + (f" (using `{', '.join(ap['index_names'])}`)" if ap["index_names"] else "") + "\n"
        f"- **Same rows returned before and after:** {'yes ✅' if r['same_result'] else 'no ❌'}"
    )
    if case.fix:
        st.markdown("**Fix that was applied:**")
        st.code(";\n".join(s for s in case.fix if not s.startswith("CREATE EXTENSION")) + ";", language="sql")
    else:
        st.markdown("**Rewritten query** (no schema change needed):")
        st.code(case.after.replace("%(", ":").replace(")s", ""), language="sql")

st.markdown(
    "Timings are the median of 5 warm runs on this small free server. On the full 2-million-order dataset in the "
    "[case study](https://github.com/Zotriq/postgres-performance-tuning#results) the gaps are bigger (22x – 460x), "
    "because the slow versions read the whole table and the fixed ones don't.",
    help=None,
)
ui.footer()
