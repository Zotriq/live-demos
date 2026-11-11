import altair as alt
import pandas as pd
import streamlit as st

from ops import core, style

w = core.ws()
style.title("Sales pipeline", "Every deal across the agency's offers in one pipeline, the same way it would live in GoHighLevel.")

deals = [l for l in w.leads if not l["stream"].startswith("Lead Desk")]
streams = sorted({l["stream"] for l in deals})
pick = st.segmented_control("Offer", ["All"] + streams, default="All", label_visibility="collapsed") or "All"
shown = [l for l in deals if pick == "All" or l["stream"] == pick]

won = [l for l in shown if l["stage"] == "Won"]
open_ = [l for l in shown if l["stage"] not in ("Won", "Lost")]
k = st.columns(4)
k[0].metric("Open deals", len(open_), border=True)
k[1].metric("Open value", f"${sum(l['value'] for l in open_):,.0f}", border=True)
k[2].metric("Won", len(won), f"${sum(l['value'] for l in won):,.0f}", delta_color="off", border=True)
k[3].metric("Win rate", f"{len(won) / max(1, len([l for l in shown if l['stage'] in ('Won', 'Lost')])):.0%}", "of closed deals",
            delta_color="off", border=True)

cols = []
for stage in core.STAGES[:-1]:
    items = [l for l in shown if l["stage"] == stage]
    cards = "".join(f'<div class="card"><b>{style.esc(l["company"])}</b>{style.esc(l["name"])} · &#36;{l["value"]:,}'
                    f'<div class="m">{style.esc(l["stream"])} · {style.esc(l["source"])} · {style.ago(l["created"])}</div></div>'
                    for l in items)
    cols.append(f'<div class="col"><div class="ch"><span>{stage}</span><span style="opacity:.55">{len(items)}</span></div>{cards}</div>')
st.markdown(f'<div class="kanban">{"".join(cols)}</div>', unsafe_allow_html=True)

st.write("")
a, b = st.columns(2, gap="large")
with a:
    st.subheader("Move a deal")
    with st.form("move", border=True):
        ids = [l["id"] for l in shown if l["stage"] not in ("Won", "Lost")]
        deal = st.selectbox("Deal", ids, format_func=lambda i: f"{w.lead(i)['company']} ({w.lead(i)['stage']})") if ids else None
        stage = st.selectbox("New stage", core.STAGES)
        if st.form_submit_button("Update", type="primary") and deal:
            l = w.lead(deal)
            l["stage"] = stage
            w.event(f"{l['company']} moved to {stage}", "win" if stage == "Won" else "info")
            st.rerun()
with b:
    st.subheader("Where deals come from")
    src = pd.DataFrame([{"source": l["source"], "stage": "Won" if l["stage"] == "Won" else "Open or lost"} for l in shown])
    if not src.empty:
        st.altair_chart(alt.Chart(src).mark_bar(cornerRadiusEnd=4).encode(
            y=alt.Y("source:N", title=None, sort="-x"), x=alt.X("count():Q", title="Deals"),
            color=alt.Color("stage:N", title=None, scale=alt.Scale(domain=["Won", "Open or lost"], range=["#d9480f", "#e9d8c8"]),
                            legend=alt.Legend(orient="bottom"))).properties(height=200), width="stretch")
