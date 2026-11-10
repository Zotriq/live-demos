"""Glow Desk look: berry and cream, Fraunces headings, WhatsApp-style chat."""

from __future__ import annotations

import datetime as dt
import html
import json

import streamlit as st

from .core import REPO, SERVICES, local_now
from lib.ui import PORTFOLIO, UPWORK

CSS = """
<style>
h1, h2, h3 { letter-spacing: -0.01em; }
.block-container { padding-top: 2.4rem; max-width: 1240px; }
.brand { display:flex; align-items:center; gap:10px; padding: 2px 0 10px; }
.brand .mark { width:36px; height:36px; border-radius:10px; background: linear-gradient(135deg,#8b3a62,#c2577f);
  display:flex; align-items:center; justify-content:center; color:#fff; font-weight:700; font-family:'Fraunces',serif; font-size:20px; }
.brand b { font-family:'Fraunces',serif; font-size:19px; display:block; line-height:1.1; }
.brand span { font-size:12px; opacity:.65; }
.side-foot { font-size:12px; opacity:.7; line-height:1.6; padding-top: 8px; }
.side-foot a { color: inherit !important; }
.sub { opacity:.72; margin-top:-10px; margin-bottom: 14px; font-size: 15px; }
.pill { display:inline-block; font-size:12px; font-weight:600; padding:2px 9px; border-radius:999px; line-height:1.6; }
.pill.bot { background:#e7f3ec; color:#1f6b43; } .pill.human { background:#fde8e4; color:#a33a26; }
.pill.ai { background:#f5e6ee; color:#8b3a62; } .pill.desk { background:#eef0f6; color:#3c4a7a; } .pill.call { background:#fff3dc; color:#8a5a00; }
.pill.up { background:#e6f0fb; color:#1f5aa6; } .pill.done { background:#ececec; color:#555; } .pill.cancel { background:#fde8e4; color:#a33a26; }
.feed { font-size:14px; line-height:1.45; }
.feed div { padding:7px 0; border-bottom:1px solid rgba(0,0,0,.06); display:flex; gap:10px; }
.feed time { opacity:.55; min-width: 96px; font-size:12px; padding-top:2px; }
/* chat */
.wa { background:#efeae2; border-radius:12px; padding:14px 16px; }
.wa-day { text-align:center; margin:10px 0; } .wa-day span { background:#fff; font-size:11.5px; padding:3px 10px; border-radius:8px; color:#54656f; box-shadow:0 1px .5px rgba(0,0,0,.1);}
.wa-row { display:flex; margin:4px 0; } .wa-row.out { justify-content:flex-end; }
.wa-b { max-width:76%; padding:6px 9px 4px; border-radius:8px; font-size:14.5px; line-height:1.38; color:#111b21;
  box-shadow:0 1px .5px rgba(0,0,0,.13); white-space:pre-wrap; word-wrap:break-word; }
.wa-row.out .wa-b { background:#d9fdd3; } .wa-row.in .wa-b { background:#fff; }
.wa-row.staff .wa-b { background:#fbe7f0; border:1px solid #f0c9da; }
.wa-who { font-size:11.5px; font-weight:700; color:#8b3a62; margin-bottom:1px; }
.wa-t { font-size:10.5px; color:#667781; text-align:right; margin-top:1px; }
.wa-tool { text-align:center; margin:3px 0; } .wa-tool span { font-size:11.5px; background:#fdf6e3; color:#6b5a2a; border:1px solid #efe2b8;
  padding:2px 9px; border-radius:7px; font-family: ui-monospace, Menlo, monospace; }
.wa-head { display:flex; gap:10px; align-items:center; background:#075e54; color:#fff; padding:10px 14px; border-radius:12px 12px 0 0; }
.wa-head .av { width:34px; height:34px; border-radius:50%; background:#dfe5e7; color:#54656f; display:flex; align-items:center; justify-content:center; font-weight:700; }
.wa-head b { font-size:15px; display:block; } .wa-head span { font-size:12px; opacity:.85; }
.wa.joined { border-radius: 0 0 12px 12px; }
/* phone */
.phone { width: 360px; max-width:100%; margin: 0 auto; border: 11px solid #1f1a1d; border-radius: 42px; overflow:hidden; background:#efeae2;
  box-shadow: 0 18px 40px rgba(60,20,40,.18); }
.phone .bar { background:#075e54; color:#fff; font-size:11px; padding:6px 18px 0; display:flex; justify-content:space-between; }
.phone .wa-head { border-radius:0; }
.phone .wa { border-radius:0; height: 400px; overflow-y:auto; display:flex; flex-direction:column; }
.phone .wa .spacer { flex:1; }
/* schedule grid */
.grid { width:100%; border-collapse:separate; border-spacing:0; font-size:13px; }
.grid th { text-align:left; font-weight:600; padding:6px 8px; border-bottom:2px solid #eadfd9; }
.grid td { border-bottom:1px solid #f1e9e5; padding:0 6px; height:36px; vertical-align:top; }
.grid td.time { width:70px; opacity:.6; font-size:12px; padding-top:4px; }
.slot { border-radius:7px; padding:4px 8px; margin:3px 0; box-sizing:border-box; color:#2a1f24; font-size:12px; line-height:1.3; overflow:hidden; }
.slot b { display:block; } .slot.past { opacity:.55; }
.svc-haircut { background:#f5e6ee; border-left:4px solid #8b3a62; } .svc-color { background:#fff0dc; border-left:4px solid #c27a12; }
.svc-facial { background:#e6f3ee; border-left:4px solid #2f8a5e; } .svc-manicure { background:#e9ecf8; border-left:4px solid #4c5fb0; }
.svc-bridal { background:#fbe9e7; border-left:4px solid #c2493a; }
.kv { font-size:14px; line-height:1.9; } .kv b { display:inline-block; min-width: 92px; font-weight:600; opacity:.7; }
.step { border-left:3px solid #e2cfd8; padding:2px 0 10px 14px; position:relative; font-size:14px; }
.step:before { content:""; position:absolute; left:-7px; top:5px; width:11px; height:11px; border-radius:50%; background:#8b3a62; }
.step code { font-size:12px; white-space: pre-wrap; }
</style>
"""

PILL = {"bot": ("AI handling", "bot"), "human": ("Needs a person", "human"), "AI agent": ("AI agent", "ai"),
        "Front desk": ("Front desk", "desk"), "Phone call": ("Phone call", "call"), "Upcoming": ("Upcoming", "up"),
        "In progress": ("In chair now", "ai"), "Completed": ("Completed", "done"), "Cancelled": ("Cancelled", "cancel")}

TOOL_LABEL = {"list_services": "looked up services & prices", "check_availability": "checked availability",
              "book_appointment": "booked appointment", "my_bookings": "looked up bookings",
              "cancel_booking": "cancelled booking", "handoff_to_human": "handed to staff"}


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def sidebar() -> None:
    with st.sidebar:
        st.markdown(
            f'<div class="side-foot">Glow Desk is a portfolio demo of my <a href="{REPO}" target="_blank">WhatsApp AI agent</a>. '
            f'The AI replies come from a real language model; the salon and its customers are sample data, private to you.'
            f'<br><br>Built by <a href="{PORTFOLIO}" target="_blank">Zohaib Tariq</a> · <a href="{UPWORK}" target="_blank">Hire me on Upwork</a></div>',
            unsafe_allow_html=True)


def title(text: str, sub: str | None = None) -> None:
    st.markdown(f"# {text}")
    if sub:
        st.markdown(f'<div class="sub">{sub}</div>', unsafe_allow_html=True)


def pill(key: str) -> str:
    label, cls = PILL.get(key, (key, "done"))
    return f'<span class="pill {cls}">{html.escape(label)}</span>'


def ago(t: dt.datetime) -> str:
    secs = (local_now() - t).total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if t.date() == local_now().date():
        return t.strftime("%-I:%M %p")
    if t.date() == local_now().date() - dt.timedelta(days=1):
        return "Yesterday"
    return t.strftime("%d %b")


def stamp(t: dt.datetime) -> str:
    today = local_now().date()
    if t.date() == today:
        return t.strftime("%-I:%M %p")
    return ("Yesterday " if t.date() == today - dt.timedelta(days=1) else t.strftime("%d %b ")) + t.strftime("%-I:%M %p")


def day_label(d: dt.date) -> str:
    today = local_now().date()
    return "Today" if d == today else "Yesterday" if d == today - dt.timedelta(days=1) else d.strftime("%A, %d %B")


def tool_text(call: dict) -> str:
    name = call["function"]["name"]
    try:
        args = json.loads(call["function"].get("arguments") or "{}")
    except ValueError:
        args = {}
    bits = []
    if "service" in args and args["service"] in SERVICES:
        bits.append(SERVICES[args["service"]]["label"].lower())
    for k in ("date", "time", "code", "reason"):
        if args.get(k):
            bits.append(str(args[k]))
    text = f"⚙ {TOOL_LABEL.get(name, name)}" + (f" · {', '.join(bits)}" if bits else "")
    return text if len(text) <= 72 else text[:70] + "…"


def chat(messages: list[dict], customer_view: bool = False, tools: bool = True, staff_name: str = "Staff") -> str:
    """WhatsApp-style transcript. Business view: customer on the left. Customer view (phone): customer on the right."""
    out, day = [], None
    for m in messages:
        if m["role"] == "tool":
            continue
        if m["at"].date() != day:
            day = m["at"].date()
            out.append(f'<div class="wa-day"><span>{day_label(day)}</span></div>')
        t = m["at"].strftime("%-I:%M %p")
        if m["role"] == "assistant" and m["tool_calls"]:
            if tools and not customer_view:
                out += [f'<div class="wa-tool"><span>{html.escape(tool_text(c))}</span></div>' for c in m["tool_calls"]]
            if not m["content"]:
                continue
        if not m["content"]:
            continue
        body = html.escape(m["content"]).replace("*", "")
        if m["role"] == "user":
            side = "out" if customer_view else "in"
            out.append(f'<div class="wa-row {side}"><div class="wa-b">{body}<div class="wa-t">{t}{" ✓✓" if customer_view else ""}</div></div></div>')
        else:
            side = "in" if customer_view else "out"
            who = ""
            if not customer_view:
                who = {"staff": f"{staff_name} (staff)", "system": "Automatic message"}.get(m["kind"], "AI assistant")
                who = f'<div class="wa-who">{who}</div>'
            cls = " staff" if m["kind"] == "staff" else ""
            out.append(f'<div class="wa-row {side}{cls}"><div class="wa-b">{who}{body}<div class="wa-t">{t}{"" if customer_view else " ✓✓"}</div></div></div>')
    return "".join(out)


def initials(name: str) -> str:
    parts = [p for p in name.split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"
