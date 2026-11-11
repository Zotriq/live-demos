import pandas as pd
import streamlit as st

from ui.common import get_store, header

store = get_store()
header("Monitoring", "Run history", "Every scheduled or manual run, what it found, and anything that failed.")

runs = store.runs(100)
if not runs:
    st.info("No runs yet.", icon=":material/info:")
    st.stop()

df = pd.DataFrame(runs)
df["started"] = pd.to_datetime(df["started_at"], utc=True).dt.tz_convert(None)
df["duration"] = (pd.to_datetime(df["finished_at"], utc=True) - pd.to_datetime(df["started_at"], utc=True)).dt.total_seconds().round(1)
df["errors_n"] = df["errors"].map(lambda e: len(e or []))
df["run"] = df["id"].map(lambda i: f"#{i}")

chart = df.sort_values("id")[["run", "new", "duplicates", "updated"]].set_index("run")
chart.columns = ["New", "Duplicates skipped", "Changed"]
st.markdown("**New vs already-known jobs per run**")
st.bar_chart(chart, color=["#2563eb", "#cbd5e1", "#f59e0b"], height=260, stack=True)

st.dataframe(
    df[["run", "started", "mode", "fetched", "new", "duplicates", "updated", "closed", "scored_llm", "scored_rules", "alerts", "errors_n", "duration"]],
    hide_index=True, width="stretch",
    column_config={
        "run": "Run", "started": st.column_config.DatetimeColumn("Started (UTC)", format="MMM D, HH:mm:ss"),
        "mode": "Mode", "fetched": "Fetched", "new": "New", "duplicates": "Duplicates", "updated": "Changed",
        "closed": "Closed", "scored_llm": "AI scored", "scored_rules": "Rule scored", "alerts": "Alerts",
        "errors_n": "Errors", "duration": st.column_config.NumberColumn("Seconds", format="%.1f"),
    })

failed = [(r["id"], e) for r in runs for e in (r["errors"] or [])]
if failed:
    with st.expander(f"Source errors ({len(failed)})"):
        for rid, e in failed:
            st.markdown(f"- Run #{rid}: {e}")
