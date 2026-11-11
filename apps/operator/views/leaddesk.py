import json

import pandas as pd
import streamlit as st

from lib import llm
from ops import core, leaddesk, style

w = core.ws()
style.title("Lead Desk", f"Built for an agency client, {leaddesk.CLIENT}. Every new lead (missed call, web form, ad) gets a text "
            "within seconds; the AI qualifies the job and books the visit straight into the client's calendar.")

desk = [l for l in w.leads if l["stream"].startswith("Lead Desk")]
booked = [l for l in desk if l["fields"].get("booked")]
k = st.columns(4)
k[0].metric("Leads handled", len(desk), border=True)
k[1].metric("First reply in", f"{sum(l['first_reply_secs'] or 0 for l in desk) / max(1, len(desk)):.0f} sec", "average", delta_color="off", border=True)
k[2].metric("Booked by the AI", f"{len(booked) / max(1, len(desk)):.0%}", f"{len(booked)} visits", delta_color="off", border=True)
k[3].metric("Pipeline value", f"${sum(l['value'] for l in desk):,.0f}", "estimated jobs", delta_color="off", border=True)

left, mid, right = st.columns([1.05, 1.25, 1.25], gap="large")
with left:
    st.markdown("**New lead**")
    with st.form("new_lead", border=True):
        source = st.selectbox("Came in from", ["Missed call", "Website form", "Facebook ad"])
        name = st.text_input("Name (optional)", "Jordan Miles")
        note = st.text_input("What they said or picked", "AC stopped working")
        go = st.form_submit_button("Send it to the Lead Desk", type="primary", width="stretch")
    if go and not core.need_key():
        lead = w.add_lead(company="Homeowner", name=name.strip(), phone="+1 (504) 555-0199", stream="Lead Desk (Polar Peak)",
                          source=source, notes=note.strip(), value=89)
        w.active_lead = lead["id"]
        try:
            with st.spinner("Texting the lead…"):
                st.session_state.desk_trace = leaddesk.reply(w, lead, None)
        except Exception as exc:  # noqa: BLE001
            llm.friendly_error(exc)
        st.rerun()
    st.markdown("**Leads**")
    ids = [l["id"] for l in desk]
    current = w.active_lead if w.active_lead in ids else ids[0]
    pick = st.radio("Leads", ids, index=ids.index(current), label_visibility="collapsed",
                    format_func=lambda i: f"{w.lead(i)['name'] or 'Unknown'} · {w.lead(i)['stage']} · {style.ago(w.lead(i)['created'])}")
    if pick != w.active_lead:
        w.active_lead = pick
        st.session_state.pop("desk_trace", None)

lead = w.lead(w.active_lead or ids[0])
with mid:
    st.markdown(style.sms(lead["messages"], leaddesk.CLIENT, "Text message"), unsafe_allow_html=True)
    examples = ["It's blowing warm air and it's really hot in here", "Can someone come tomorrow morning?",
                "I'm in Metairie, the unit is maybe 10 years old", "I smell gas near the furnace"]
    ex = st.pills("Reply as the homeowner", examples, key=f"ex_{lead['id']}_{len(lead['messages'])}")
    typed = st.chat_input("Reply as the homeowner…")
    text = typed or ex
    if text and not core.need_key():
        try:
            with st.spinner("The AI is replying…"):
                st.session_state.desk_trace = leaddesk.reply(w, lead, text)
        except Exception as exc:  # noqa: BLE001
            llm.friendly_error(exc)
        st.rerun()

with right:
    with st.container(border=True):
        st.markdown(f"**{style.esc(lead['name'] or 'Unknown')}** · {lead['source']}")
        f = lead["fields"]
        rows = [("Stage", lead["stage"]), ("Issue", f.get("issue")), ("Urgency", f.get("urgency")), ("System age", f.get("system_age")),
                ("Area", f.get("address")), ("Booked", f.get("booked")), ("Est. value", f"${lead['value']:,}" if lead["value"] else None),
                ("First reply", f"{lead['first_reply_secs']} sec" if lead["first_reply_secs"] else None), ("Owner alert", f.get("handoff"))]
        st.markdown('<div class="kv">' + "<br>".join(f"<b>{k}</b> {style.esc(v)}" for k, v in rows if v) + "</div>", unsafe_allow_html=True)
        if f.get("booked") and lead["stage"] != "Won" and st.button("Job done: ask for a Google review", width="stretch"):
            if not core.need_key():
                try:
                    leaddesk.review_request(w, lead)
                except Exception as exc:  # noqa: BLE001
                    llm.friendly_error(exc)
                st.rerun()
    st.markdown("**Behind the scenes**")
    trace = st.session_state.get("desk_trace")
    if trace and w.active_lead == lead["id"]:
        steps = [f'<div class="step"><b>{s["tool"]}</b><br><code>in: {style.esc(json.dumps(s["args"]))}\nout: '
                 f'{style.esc(json.dumps(s["result"])[:300])}</code></div>' for s in trace["trace"]]
        steps.append(f'<div class="step"><b>Text sent</b> · {trace["secs"]} s after the message arrived</div>')
        st.markdown("".join(steps), unsafe_allow_html=True)
    else:
        st.caption("Send a lead or a reply: every tool the AI uses (availability, booking, saving lead details, owner alerts) "
                   "shows here with its real inputs and outputs.")

st.subheader(f"{leaddesk.CLIENT}: technician calendar")
days = sorted({j["date"] for j in w.jobs})[:6]
grid = []
for win in leaddesk.WINDOWS:
    row = {"Window": win}
    for d in days:
        jobs = [j for j in w.jobs if j["date"] == d and j["window"] == win]
        row[f"{d:%a %b %-d}"] = " · ".join(f"{'🤖 ' if j['source'] == 'Lead Desk (AI)' else ''}{j['tech']}: {j['issue']}" for j in jobs) or "Free"
    grid.append(row)
st.dataframe(pd.DataFrame(grid), hide_index=True, width="stretch")
st.caption("🤖 = booked by the Lead Desk AI. Two technicians, five 2-hour windows a day, Monday to Saturday.")
