"""Shared look and helpers for the Streamlit pages."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from radar.config import is_public, load_profile
from radar.notify import Slack
from radar.scoring import LLMScorer
from radar.store import Store

CSS = """
<style>
:root { --jr-ink:#0f172a; --jr-muted:#64748b; --jr-line:#e2e8f0; --jr-card:#ffffff; --jr-accent:#2563eb; }
.block-container { padding-top: 3.2rem; max-width: 1280px; }
h1, h2, h3 { letter-spacing: -0.01em; }
.jr-eyebrow { color: var(--jr-accent); font-weight: 600; font-size: .8rem; letter-spacing: .08em; text-transform: uppercase; margin-bottom: .1rem; }
.jr-sub { color: var(--jr-muted); font-size: 1rem; margin-top: -.4rem; margin-bottom: 1.2rem; }
.jr-pill { display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600; margin: 0 6px 6px 0; border: 1px solid var(--jr-line); background: #f8fafc; color: #334155; }
.jr-pill.ok { background:#ecfdf5; border-color:#a7f3d0; color:#047857; }
.jr-pill.warn { background:#fffbeb; border-color:#fde68a; color:#b45309; }
.jr-pill.off { background:#f1f5f9; color:#64748b; }
.jr-score { display:inline-block; min-width: 44px; text-align:center; padding: 2px 8px; border-radius: 8px; font-weight: 700; font-size: .85rem; }
.jr-score.s-hi { background:#dcfce7; color:#166534; } .jr-score.s-mid { background:#fef9c3; color:#854d0e; }
.jr-score.s-lo { background:#ffedd5; color:#9a3412; } .jr-score.s-no { background:#f1f5f9; color:#475569; }
.jr-step { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .86rem; padding: 2px 0; color: #334155; }
.jr-step b { color: var(--jr-ink); }
/* Slack-style message card */
.slack { border: 1px solid var(--jr-line); border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; background: #fff; display:flex; gap: 10px; font-family: -apple-system, "Segoe UI", Lato, sans-serif; }
.slack .av { width: 36px; height: 36px; border-radius: 8px; background: linear-gradient(135deg,#2563eb,#7c3aed); color:#fff; font-weight:800; display:flex; align-items:center; justify-content:center; font-size:.8rem; flex: none; }
.slack .hd { font-size: .9rem; } .slack .hd b { color:#1d1c1d; } .slack .app { background:#e8e8e8; color:#616061; font-size:.62rem; font-weight:700; padding:1px 4px; border-radius:3px; margin: 0 4px; }
.slack .tm { color:#616061; font-size:.75rem; }
.slack .tx { color:#1d1c1d; font-size: .92rem; line-height: 1.45; margin-top: 3px; }
.slack .tx a { color:#1264a3; text-decoration:none; font-weight:700; }
.slack .flds { display:grid; grid-template-columns: 120px 1fr; gap: 6px 18px; margin-top: 8px; font-size: .88rem; color:#1d1c1d; }
.slack .ctx { color:#616061; font-size: .76rem; margin-top: 8px; }
.slack .btn { display:inline-block; border:1px solid #c7c7c7; border-radius:6px; padding: 3px 12px; font-size:.82rem; font-weight:600; color:#1d1c1d; margin-top: 8px; text-decoration:none; }
.slack .chan { color:#616061; font-size:.75rem; margin-left: 6px; }
.jr-hist { border-left: 2px solid var(--jr-line); padding-left: 12px; margin-left: 4px; }
.jr-hist div { margin-bottom: 8px; font-size: .9rem; }
.jr-hist .ev { font-weight: 700; } .jr-hist .when { color: var(--jr-muted); font-size: .8rem; }
div[data-testid="stMetricValue"] { font-size: 1.7rem; }
</style>
"""


def setup():
    st.markdown(CSS, unsafe_allow_html=True)
    if "mode" not in st.session_state:
        st.session_state.mode = "sample" if is_public(load_profile()) else "live"


@st.cache_resource
def get_store() -> Store:
    return Store()


def profile() -> dict:
    """Saved profile, or this visitor's own edits in public demo mode."""
    return st.session_state.get("profile_override") or load_profile()


def public() -> bool:
    return is_public(load_profile())


def header(eyebrow: str, title: str, sub: str = ""):
    st.markdown(f'<div class="jr-eyebrow">{html.escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.markdown(f"## {title}")
    if sub:
        st.markdown(f'<div class="jr-sub">{sub}</div>', unsafe_allow_html=True)


def pill(text: str, kind: str = "") -> str:
    return f'<span class="jr-pill {kind}">{html.escape(text)}</span>'


def score_html(score) -> str:
    if score is None:
        return '<span class="jr-score s-no">-</span>'
    cls = "s-hi" if score >= 85 else "s-mid" if score >= 70 else "s-lo" if score >= 40 else "s-no"
    return f'<span class="jr-score {cls}">{score}</span>'


def connections() -> dict:
    llm = LLMScorer(profile())
    slack = Slack()
    store = get_store()
    return {"llm": llm, "slack": slack, "store": store}


def sidebar_status():
    c = connections()
    with st.sidebar:
        st.markdown("#### Job Radar")
        st.caption("Job Discovery agent · demo build")
        mode = st.radio("Data", ["Live sources", "Recorded sample"],
                        index=0 if st.session_state.mode == "live" else 1,
                        help="Live calls the real public job APIs. Recorded sample replays saved API responses (works offline).")
        st.session_state.mode = "live" if mode == "Live sources" else "sample"
        st.markdown("---")
        st.markdown("**Connections**")
        st.markdown(
            (pill(f"AI: {c['llm'].label}", "ok") if c["llm"].enabled else pill("AI: off (rules only)", "warn")) + "<br>" +
            (pill(f"Slack: {c['slack'].channel}", "ok") if c["slack"].live else pill("Slack: preview mode", "warn")) + "<br>" +
            pill(f"DB: {c['store'].kind}", "ok"),
            unsafe_allow_html=True)
        if public():
            st.caption("Public demo: Slack messages are shown as previews, and live runs are limited to one every few minutes.")


# ------------------------------------------------------------- Slack rendering

def _mrkdwn(text: str) -> str:
    t = html.escape(text or "")
    t = re.sub(r"&lt;(https?://[^|&]+?)\|(.+?)&gt;", r'<a href="\1" target="_blank">\2</a>', t)
    t = re.sub(r"\*(.+?)\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![a-z0-9])_(.+?)_(?![a-z0-9])", r"<i>\1</i>", t)
    return t.replace("\n", "<br>")


def slack_card(payload: dict, when: datetime | None = None, channel: str = "", status: str = "") -> str:
    when = when or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    t = when.astimezone().strftime("%I:%M %p").lstrip("0")
    parts = []
    for b in payload.get("blocks", []):
        typ = b.get("type")
        if typ == "header":
            parts.append(f'<div class="tx" style="font-size:1.05rem"><b>{html.escape(b["text"]["text"])}</b></div>')
        elif typ == "section":
            if b.get("text"):
                parts.append(f'<div class="tx">{_mrkdwn(b["text"]["text"])}</div>')
            if b.get("fields"):
                cells = []
                for f in b["fields"]:
                    label, _, value = f["text"].partition("\n")
                    cells.append(f"<div>{_mrkdwn(label)}</div><div>{_mrkdwn(value)}</div>")
                parts.append(f'<div class="flds">{"".join(cells)}</div>')
            acc = b.get("accessory")
            if acc and acc.get("type") == "button":
                parts.append(f'<a class="btn" href="{html.escape(acc.get("url", "#"))}" target="_blank">{html.escape(acc["text"]["text"])}</a>')
        elif typ == "context":
            parts.append(f'<div class="ctx">{" ".join(_mrkdwn(e.get("text", "")) for e in b.get("elements", []))}</div>')
    badge = ""
    if status:
        kind = {"sent": "ok", "preview": "warn", "failed": "warn"}.get(status, "")
        label = {"sent": "Sent to Slack", "preview": "Preview", "failed": "Failed"}.get(status, status)
        badge = f'<span class="jr-pill {kind}" style="margin-left:8px">{label}</span>'
    return (f'<div class="slack"><div class="av">JR</div><div style="flex:1">'
            f'<div class="hd"><b>Job Radar</b><span class="app">APP</span><span class="tm">{t}</span>'
            f'<span class="chan">{html.escape(channel)}</span>{badge}</div>{"".join(parts)}</div></div>')


# ------------------------------------------------------------- tables

SOURCE_NAMES = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "remotive": "Remotive"}


def jobs_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["source_name"] = df["source"].map(lambda s: SOURCE_NAMES.get(s, s))
    df["sources_count"] = df["seen_on"].map(lambda v: len(v or []))
    df["status"] = df.apply(lambda r: "Alerted" if r["alerted_at"] is not None else ("Closed" if not r["is_active"] else "Stored"), axis=1)
    for col in ("salary", "employment_type", "department"):
        df[col] = df[col].fillna("")
    df["first_seen_local"] = pd.to_datetime(df["first_seen"], utc=True).dt.tz_convert(None)
    return df


JOB_COLUMNS = {
    "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d", width="small"),
    "title": st.column_config.TextColumn("Job title", width="medium"),
    "company": st.column_config.TextColumn("Company"),
    "location": st.column_config.TextColumn("Location", width="medium"),
    "salary": st.column_config.TextColumn("Salary"),
    "score_reason": st.column_config.TextColumn("Why it scored", width="large"),
    "source_name": st.column_config.TextColumn("Source", width="small"),
    "status": st.column_config.TextColumn("Status", width="small"),
    "url": st.column_config.LinkColumn("Link", display_text="Open", width="small"),
}


def ago(dt) -> str:
    if dt is None:
        return "never"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = (datetime.now(timezone.utc) - dt).total_seconds()
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)} min ago"
    if s < 86400:
        return f"{int(s // 3600)} h ago"
    return f"{int(s // 86400)} d ago"
