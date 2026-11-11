import datetime as dt
import json

import altair as alt
import pandas as pd
import streamlit as st

from lib import llm
from ops import core, style

w = core.ws()
t = core.now()
style.title("Command centre", f"{core.AGENCY} · week of {(t - dt.timedelta(days=t.weekday())):%B %-d} · "
            "seven income streams, run as three businesses")

wk = pd.DataFrame(w.weekly)
wk["group"] = wk["stream"].map(core.STREAM_GROUP)
weeks = sorted(wk["week"].unique())
this, last = weeks[-1], weeks[-2]
rev_this = wk[wk["week"] == this]["revenue"].sum()
rev_last = wk[wk["week"] == last]["revenue"].sum()
agency_leads = [l for l in w.leads if not l["stream"].startswith("Lead Desk")]
open_leads = [l for l in agency_leads if l["stage"] not in ("Won", "Lost")]
retainers = sum(1 for l in agency_leads if l["stage"] == "Won")
desk = [l for l in w.leads if l["stream"].startswith("Lead Desk") and l["first_reply_secs"]]
founder = [x for x in w.tasks if x["type"] == "Founder" and x["status"] != "Done"]

k = st.columns(5)
k[0].metric("Revenue this week", f"${rev_this:,.0f}", f"{(rev_this - rev_last) / max(1, rev_last):+.0%} vs last wk", border=True)
k[1].metric("Monthly recurring", f"${retainers * 497 + 4 * 297:,.0f}", f"+{retainers} retainers", border=True)
k[2].metric("Open pipeline", f"${sum(l['value'] for l in open_leads):,.0f}", f"{len(open_leads)} deals", delta_color="off", border=True)
k[3].metric("Lead response time", f"{sum(l['first_reply_secs'] for l in desk) / max(1, len(desk)):.0f} sec",
            "AI replies", delta_color="off", border=True)
k[4].metric("Founder decisions", len(founder), "this week", delta_color="off", border=True)

cols = st.columns(3, gap="medium")
for col, (group, streams) in zip(cols, core.GROUPS.items()):
    g = wk[wk["group"] == group]
    month = g[g["week"].isin(weeks[-4:])]["revenue"].sum()
    rows = "".join(f'<div class="row"><span>{s}</span><b>${g[(g["stream"] == s) & g["week"].isin(weeks[-4:])]["revenue"].sum():,.0f}</b></div>'
                   for s in streams)
    col.markdown(f'<div class="group">{style.chip(group, style.GROUP_CLS[group])}<div class="big">${month:,.0f}</div>'
                 f'<div style="font-size:12.5px;opacity:.6;margin-bottom:6px">last 4 weeks</div>{rows}</div>', unsafe_allow_html=True)

st.write("")
left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Weekly revenue by business")
    g = wk.groupby(["week", "group"], as_index=False)["revenue"].sum()
    g["week"] = pd.to_datetime(g["week"])
    st.altair_chart(alt.Chart(g).mark_bar(size=26, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("week:T", title=None, axis=alt.Axis(format="%b %d", labelAngle=0)),
        y=alt.Y("revenue:Q", title="USD", stack=True),
        color=alt.Color("group:N", title=None, scale=alt.Scale(domain=list(core.GROUPS), range=["#d9480f", "#4a74c9", "#4e9a63"]),
                        legend=alt.Legend(orient="top")),
        tooltip=["week:T", "group", alt.Tooltip("revenue:Q", format="$,.0f")]).properties(height=280), width="stretch")

    st.subheader("Decisions waiting for the founder")
    for x in founder:
        st.markdown(f"- **{x['task']}** · {x['stream']} · due {x['due']:%a %b %-d}")

with right:
    st.subheader("Monday brief")
    if st.button("Write this week's brief with AI", icon=":material/auto_awesome:", type="primary", width="stretch"):
        if not core.need_key():
            facts = {
                "revenue_by_stream": {s: {"last_week": int(wk[(wk["stream"] == s) & (wk["week"] == last)]["revenue"].sum()),
                                          "this_week": int(wk[(wk["stream"] == s) & (wk["week"] == this)]["revenue"].sum())}
                                      for s in core.STREAM_GROUP},
                "pipeline": pd.Series([l["stage"] for l in agency_leads]).value_counts().to_dict(),
                "open_tasks": [f"{x['task']} ({x['owner']}, {x['status']})" for x in w.tasks if x["status"] != "Done"],
                "recent_events": [e["text"] for e in w.events[:6]],
            }
            try:
                with st.spinner("Reading the numbers…"):
                    w.brief = core.ask_text(
                        "You are the operator of a small AI agency writing the founder's Monday brief. She is busy (full-time job, baby). "
                        "Write: 1) one-line headline with the key number, 2) 'What moved' (3 bullets), 3) 'This week's focus' (3 bullets, "
                        "revenue first), 4) 'I need from you' (at most 2 yes/no decisions). Plain words, under 170 words, markdown.",
                        [{"role": "user", "content": json.dumps(facts, default=str)}])
            except Exception as exc:  # noqa: BLE001
                llm.friendly_error(exc)
    with st.container(border=True):
        st.markdown(w.brief or "*Press the button: the AI reads this week's numbers, pipeline and tasks and writes a 1-minute "
                               "brief for the founder, so the weekly check-in takes 10 minutes.*")
    st.subheader("Live activity")
    icons = {"win": "🟢", "ai": "🤖", "alert": "🔴", "info": "•"}
    st.markdown('<div class="feed">' + "".join(f"<div><time>{style.ago(e['at'])}</time><span>{icons.get(e['kind'], '•')} "
                                               f"{style.esc(e['text'])}</span></div>" for e in w.events[:8]) + "</div>",
                unsafe_allow_html=True)
