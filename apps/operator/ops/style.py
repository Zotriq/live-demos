"""Operator OS look: warm paper, burnt orange, Bricolage Grotesque headings."""

from __future__ import annotations

import datetime as dt
import html

import streamlit as st

from lib.ui import PORTFOLIO, UPWORK

CSS = """
<style>
.block-container { padding-top: 2.2rem; max-width: 1280px; }
h1, h2, h3 { letter-spacing: -0.02em; }
.sub { opacity:.72; margin-top:-10px; margin-bottom: 16px; font-size: 15px; }
.side-foot { font-size:12px; opacity:.72; line-height:1.6; padding-top: 6px; }
.side-foot a { color: inherit !important; }
.chip { display:inline-block; font-size:11.5px; font-weight:600; padding:2px 8px; border-radius:6px; line-height:1.6; margin-right:4px; }
.g-agency { background:#fde8dc; color:#a63c0b; } .g-lead { background:#e6eefc; color:#2c56a8; } .g-bg { background:#e7f3e9; color:#2f7a45; }
.t-Contractor { background:#efe9ff; color:#5b3fc4; } .t-AI.agent, .t-AI { background:#fde8dc; color:#a63c0b; }
.t-Automation { background:#e4f4f7; color:#13707f; } .t-Founder { background:#fff1d6; color:#8a5a00; } .t-Operator { background:#e6eefc; color:#2c56a8; }
.kanban { display:grid; grid-template-columns: repeat(6, minmax(135px, 1fr)); gap:10px; overflow-x:auto; }
.col { background:#f3eee7; border-radius:12px; padding:10px; min-height:260px; }
.col .ch { font-size:13px; font-weight:700; margin:0 0 8px; display:flex; justify-content:space-between; }
.card { background:#fff; border:1px solid #ebe3d8; border-radius:9px; padding:8px 10px; margin-bottom:8px; font-size:12.5px; line-height:1.35; }
.card b { font-size:13px; display:block; } .card .m { opacity:.65; font-size:11.5px; margin-top:3px; }
.feed div { padding:7px 0; border-bottom:1px solid rgba(0,0,0,.06); font-size:14px; display:flex; gap:10px; }
.feed time { opacity:.55; min-width: 70px; font-size:12px; padding-top:2px; }
.group { border:1px solid #ebe3d8; border-radius:14px; padding:14px 16px; background:#fff; height:100%; }
.group .big { font-size:28px; font-weight:700; font-family:'Bricolage Grotesque', sans-serif; }
.group .row { display:flex; justify-content:space-between; font-size:13.5px; padding:3px 0; border-bottom:1px dashed #eee4d6; }
/* phone */
.phone { width: 340px; max-width:100%; margin: 0 auto; border: 10px solid #1d1b19; border-radius: 40px; overflow:hidden; background:#fff;
  box-shadow: 0 18px 40px rgba(60,30,10,.16); }
.phone .top { background:#f6f6f6; padding:10px 14px 8px; text-align:center; border-bottom:1px solid #e6e6e6; font-size:13px; }
.phone .top b { display:block; font-size:14px; }
.sms { height: 420px; overflow-y:auto; display:flex; flex-direction:column-reverse; padding:10px 12px; background:#fff; }
.bub { max-width:78%; padding:7px 11px; border-radius:17px; font-size:14px; line-height:1.35; margin:3px 0; white-space:pre-wrap; }
.bub.ai { background:#e9e9eb; color:#111; align-self:flex-start; border-bottom-left-radius:5px; }
.bub.lead { background:#1d8cf8; color:#fff; align-self:flex-end; border-bottom-right-radius:5px; }
.step { border-left:3px solid #f1d2c2; padding:2px 0 10px 14px; position:relative; font-size:13.5px; }
.step:before { content:""; position:absolute; left:-7px; top:5px; width:11px; height:11px; border-radius:50%; background:#d9480f; }
.step code { font-size:12px; white-space: pre-wrap; }
.kv { font-size:14px; line-height:1.85; } .kv b { display:inline-block; min-width: 100px; font-weight:600; opacity:.65; }
.out { border:1px solid #ebe3d8; border-radius:12px; padding:14px 16px; background:#fff; white-space:pre-wrap; font-size:14.5px; line-height:1.5; }
.out h5 { margin:0 0 6px; font-size:12px; text-transform:uppercase; letter-spacing:.06em; opacity:.6; }
.preview { border-radius:16px; overflow:hidden; border:1px solid #e5ddd2; background:#fff; }
.preview .hero { padding:22px 22px 18px; color:#fff; }
.preview .hero b { font-size:22px; display:block; font-family:'Bricolage Grotesque', sans-serif; }
.preview .body { padding:14px 22px 18px; font-size:14px; }
</style>
"""

GROUP_CLS = {"Agency (the money)": "g-agency", "Lead source": "g-lead", "Background income": "g-bg"}


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text) -> str:
    return html.escape(str(text)).replace("$", "&#36;").replace("\n", "<br>")


def sidebar() -> None:
    with st.sidebar:
        st.markdown(
            f'<div class="side-foot">Operator OS is a portfolio project: one workspace to run a small AI agency with several income '
            f'streams. Brightpath AI and its data are samples, private to you; the AI features use a real language model.'
            f'<br><br>Built by <a href="{PORTFOLIO}" target="_blank">Zohaib Tariq</a> · <a href="{UPWORK}" target="_blank">Hire me on Upwork</a></div>',
            unsafe_allow_html=True)


def title(text: str, sub: str | None = None) -> None:
    st.markdown(f"# {text}")
    if sub:
        st.markdown(f'<div class="sub">{sub}</div>', unsafe_allow_html=True)


def chip(text: str, cls: str) -> str:
    return f'<span class="chip {cls}">{esc(text)}</span>'


def ago(t: dt.datetime) -> str:
    from .core import now

    secs = (now() - t).total_seconds()
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    return f"{int(secs // 86400)} d ago"


def sms(messages: list[tuple[str, str]], who: str, sub: str) -> str:
    bubbles = "".join(f'<div class="bub {w}">{esc(t)}</div>' for w, t in messages)
    return (f'<div class="phone"><div class="top"><b>{esc(who)}</b>{esc(sub)}</div>'
            f'<div class="sms"><div style="display:flex;flex-direction:column">{bubbles}</div></div></div>')
