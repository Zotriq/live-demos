"""Relay look: indigo on cool white, Space Grotesk headings."""

from __future__ import annotations

import datetime as dt
import html

import streamlit as st

from .core import REPO, STEP, now
from lib.ui import PORTFOLIO, UPWORK

CSS = """
<style>
.block-container { padding-top: 2.3rem; max-width: 1260px; }
h1, h2, h3 { letter-spacing: -0.015em; }
.sub { opacity:.72; margin-top:-10px; margin-bottom: 14px; font-size: 15px; }
.side-foot { font-size:12px; opacity:.72; line-height:1.6; padding-top: 6px; }
.side-foot a { color: inherit !important; }
.tag { display:inline-block; font-size:11.5px; font-weight:600; padding:2px 8px; border-radius:6px; line-height:1.6; margin-right:3px; }
.st-new { background:#e8ecff; color:#3043b8; } .st-approval { background:#fff1d6; color:#8a5a00; } .st-esc { background:#fde7ea; color:#b0283f; }
.st-sent { background:#e3f5ec; color:#1d7048; } .st-rej { background:#eceef3; color:#59607a; } .st-staff { background:#e9f2fb; color:#235e96; }
.c-billing { background:#efe9ff; color:#5b3fc4; } .c-technical { background:#e4f4f7; color:#13707f; } .c-sales { background:#fff0e5; color:#a24d0f; }
.c-other { background:#f1f1f4; color:#555b70; }
.u-high { background:#fde7ea; color:#b0283f; } .u-normal { background:#f1f1f4; color:#555b70; } .u-low { background:#f1f1f4; color:#8a8fa3; }
.mail { border:1px solid #e3e6f0; border-radius:12px; padding:16px 18px; background:#fff; }
.mail .hdr { font-size:13px; opacity:.7; margin-bottom:8px; }
.mail .subj { font-weight:700; font-size:17px; margin-bottom:6px; }
.mail .body { white-space:pre-wrap; font-size:15px; line-height:1.5; }
.tl { position:relative; margin-left:6px; }
.tl .it { border-left:2px solid #dfe3f3; padding:0 0 14px 16px; position:relative; }
.tl .it:before { content:""; position:absolute; left:-7px; top:3px; width:12px; height:12px; border-radius:50%; background:#3b4fd8; border:2px solid #fff; box-shadow:0 0 0 1px #c9cff0; }
.tl .it.warn:before { background:#e5a12a; } .tl .it.done:before { background:#1d9a5c; } .tl .it.esc:before { background:#d23a52; }
.tl .who { font-weight:700; font-size:14px; } .tl .when { font-size:12px; opacity:.55; margin-left:6px; }
.tl .txt { font-size:13.5px; opacity:.85; white-space:pre-wrap; margin-top:2px; }
.kv { font-size:14px; line-height:1.85; } .kv b { display:inline-block; min-width: 92px; font-weight:600; opacity:.65; }
.feed div { padding:7px 0; border-bottom:1px solid rgba(0,0,0,.06); font-size:14px; display:flex; gap:10px; }
.feed time { opacity:.55; min-width: 74px; font-size:12px; padding-top:2px; }
.flow { display:flex; flex-wrap:wrap; gap:6px; align-items:center; font-size:13px; }
.flow span { padding:4px 10px; border-radius:7px; background:#eef0fd; border:1px solid #d7dcf7; }
.flow i { opacity:.45; font-style:normal; }
</style>
"""

STATUS_CLS = {"New": "st-new", "Needs approval": "st-approval", "Escalated": "st-esc", "Sent": "st-sent",
              "Rejected": "st-rej", "Resolved by staff": "st-staff"}
STATUS_ICON = {"New": "🔵", "Needs approval": "🟠", "Escalated": "🔴", "Sent": "🟢", "Rejected": "⚪", "Resolved by staff": "🟢"}


def esc(text) -> str:
    """HTML-escape, and stop Streamlit reading "$49 ... $245" as a maths formula."""
    return html.escape(str(text)).replace("$", "&#36;").replace("\n", "<br>")


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def sidebar() -> None:
    with st.sidebar:
        st.markdown(
            f'<div class="side-foot">Relay is a portfolio demo of my <a href="{REPO}" target="_blank">LangGraph support agents</a>. '
            f'New tickets are handled by a real language model; Lumen Analytics, its customers and its history are sample data, private to you.'
            f'<br><br>Built by <a href="{PORTFOLIO}" target="_blank">Zohaib Tariq</a> · <a href="{UPWORK}" target="_blank">Hire me on Upwork</a></div>',
            unsafe_allow_html=True)


def title(text: str, sub: str | None = None) -> None:
    st.markdown(f"# {text}")
    if sub:
        st.markdown(f'<div class="sub">{sub}</div>', unsafe_allow_html=True)


def tag(text: str, cls: str) -> str:
    return f'<span class="tag {cls}">{esc(text)}</span>'


def status(s: str) -> str:
    return tag(s, STATUS_CLS.get(s, "st-rej"))


def cat(c: str) -> str:
    return tag(c.capitalize(), f"c-{c}") if c and c != "–" else ""


def urg(u: str) -> str:
    return tag(f"{u} urgency", f"u-{u}") if u and u != "–" else ""


def ago(t: dt.datetime | None) -> str:
    if t is None:
        return "–"
    secs = (now() - t).total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    return t.strftime("%d %b")


def timeline(trace: list[dict]) -> str:
    out = []
    for s in trace:
        who, what = STEP.get(s["node"], (s["node"], ""))
        cls = "warn" if s.get("rewrite") else "done" if s["node"] == "send" else "esc" if s["node"] in ("escalate", "discard") else ""
        txt = (s["text"] or what).replace("**", "")
        out.append(f'<div class="it {cls}"><span class="who">{who}</span><span class="when">{s["at"]:%H:%M:%S}</span>'
                   f'<div class="txt">{esc(txt[:700])}</div></div>')
    return f'<div class="tl">{"".join(out)}</div>'
