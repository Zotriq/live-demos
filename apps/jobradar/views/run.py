import html

import streamlit as st

from radar import pipeline
from radar.config import ALL_SOURCES
from radar.notify import Slack
import time

from ui.common import (JOB_COLUMNS, ago, connections, get_store, header, jobs_frame, pill,
                       profile, public, slack_card)

COOLDOWN_S = 180


@st.cache_resource
def _live_gate() -> dict:
    return {"last": 0.0}


store = get_store()
prof = profile()
conn = connections()
live = st.session_state.mode == "live"

header("Job Discovery agent", "Find new jobs, skip duplicates, alert the good ones",
       f"Profile: <b>{html.escape(prof['name'])}</b> · Alert threshold {prof.get('alert_threshold', 70)}+ · "
       f"Posts to Slack <b>{html.escape(prof.get('slack_channel', '#new-jobs'))}</b>")

s = store.stats()
k = st.columns(5)
k[0].metric("Jobs in database", s["total"])
k[1].metric("Still open", s["active"])
k[2].metric("Strong matches (70+)", s["strong"])
k[3].metric("Slack alerts", s["alerts"])
k[4].metric("Last run", ago(s["last_run"]), help=f"{s['runs']} runs so far")

st.markdown("")
with st.container(border=True):
    left, right = st.columns([3, 2], gap="large")
    with left:
        if live:
            enabled = [x for x in ALL_SOURCES if prof.get("sources", {}).get(x) and not (public() and x == "remotive")]
            chosen = st.pills("Sources", options=enabled, default=enabled, selection_mode="multi",
                              format_func=lambda x: {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "remotive": "Remotive"}[x])
            boards = []
            for src in chosen or []:
                cfg = prof["sources"][src]
                items = cfg.get("search", []) if isinstance(cfg, dict) else cfg
                boards += [f"{src}:{b}" for b in items]
            st.caption(f"{len(boards)} boards and searches · " + ", ".join(b.split(':', 1)[1] for b in boards))
            snapshot = "day1"
        else:
            chosen = []
            snapshot = st.segmented_control("Recorded snapshot", ["day1", "day2"], default="day1",
                                            format_func=lambda x: {"day1": "Day 1 · first crawl", "day2": "Day 2 · next morning"}[x])
            st.caption("Real API response formats from Greenhouse, Lever, Ashby and Remotive, replayed offline. Companies are fictional.")
    with right:
        use_ai = st.toggle("AI relevance scoring", value=conn["llm"].enabled, disabled=not conn["llm"].enabled,
                           help="Needs an API key in .env. Without it, the rule scorer is used.")
        send_slack = st.toggle("Post alerts to Slack", value=True,
                               help="Off = build the messages as previews only.")
        digest = st.toggle("Send run summary to Slack", value=True)
        go = st.button("Run discovery", type="primary", icon=":material/radar:", width="stretch",
                       disabled=live and not chosen)

wait = int(_live_gate()["last"] + COOLDOWN_S - time.time()) if public() and live else 0
if go and wait > 0:
    st.warning(f"Live runs call real job APIs, so on this public demo they are limited. Try again in {wait} s, "
               "or switch the sidebar to Recorded sample.", icon=":material/timer:")
    go = False
if go and public() and live:
    _live_gate()["last"] = time.time()

if go:
    log = []
    icons = {"step": "▸", "fetch": "↓", "error": "✕", "dedup": "≡", "score": "★", "alert": "➜", "done": "✓"}
    with st.status("Discovery agent running...", expanded=True) as status:
        def on_event(kind, msg):
            st.markdown(f'<div class="jr-step">{icons.get(kind, "·")} {"<b>" if kind in ("dedup", "score", "alert", "done") else ""}'
                        f'{html.escape(msg)}{"</b>" if kind in ("dedup", "score", "alert", "done") else ""}</div>', unsafe_allow_html=True)
        slack = Slack(webhook=None if send_slack else "", channel_label=prof.get("slack_channel"))
        result = pipeline.run(store, prof, mode=st.session_state.mode, enabled=chosen, snapshot=snapshot,
                              use_llm=use_ai, slack=slack, send_digest=digest, on_event=on_event)
        status.update(label=f"Run #{result.run_id} complete · {result.new} new · {result.duplicates} duplicates skipped · {result.alerts} alerts",
                      state="error" if result.errors and result.fetched == 0 else "complete", expanded=False)
    st.session_state.last_result = result
    st.rerun()

res = st.session_state.get("last_result")
if res:
    st.markdown(f"#### Run #{res.run_id} results")
    m = st.columns(6)
    m[0].metric("Fetched", res.fetched)
    m[1].metric("New", res.new)
    m[2].metric("Duplicates skipped", res.duplicates, help="Already in the database (same fingerprint), including the same job found on two sources.")
    m[3].metric("Changed", res.updated, help="Same posting, but salary, title, location or description changed. Saved to history.")
    m[4].metric("Scored by AI", res.scored_llm, help=f"{res.scored_rules} were scored by rules only (clear misses never reach the LLM).")
    m[5].metric("Slack alerts", res.alerts)
    if res.errors:
        st.warning("Some sources failed and were skipped:\n\n" + "\n".join(f"- {e}" for e in res.errors))

    if res.new == 0 and res.updated == 0:
        st.success("Nothing new since the last run. Every job was recognised by its fingerprint, so no duplicates were saved and no alerts were sent.", icon=":material/verified:")
    else:
        tab_new, tab_slack = st.tabs([f"New and changed jobs ({res.new + res.updated})", f"Posted to Slack ({res.alerts})"])
        with tab_new:
            df = jobs_frame(store.jobs_by_ids(res.new_job_ids + res.updated_job_ids))
            if not df.empty:
                df["status"] = df.apply(lambda r: "Changed" if r["id"] in res.updated_job_ids else r["status"], axis=1)
                st.dataframe(df[["score", "title", "company", "location", "salary", "score_reason", "source_name", "status", "url"]],
                             column_config=JOB_COLUMNS, hide_index=True, width="stretch", height=min(560, 38 + 35 * len(df)))
            if res.updated:
                st.caption(f"{res.updated} existing job(s) changed. See the change history in Jobs database.")
        with tab_slack:
            if not res.alerted_job_ids:
                st.info("No new jobs crossed the alert threshold this run.")
            alerts = [a for a in store.alerts(200) if a["run_id"] == res.run_id]
            for a in alerts:
                st.markdown(slack_card(a["payload"], a["created_at"], a["channel"], a["status"]), unsafe_allow_html=True)
else:
    st.info("Pick the sources and press **Run discovery**. Press it twice to see deduplication: the second run saves nothing new.", icon=":material/info:")
