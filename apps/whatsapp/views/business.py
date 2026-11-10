import datetime as dt

import pandas as pd
import streamlit as st

from glow import core, style
from wa_agent.agent import SYSTEM
from wa_agent.tools import BUSINESS, TOOL_SCHEMAS

sb = core.sandbox()
style.title("Business & AI", "What the assistant knows about the salon, and the rules it follows.")

with st.container(border=True):
    a, b = st.columns([4, 1], vertical_alignment="center")
    a.markdown("**AI auto-reply**  \nWhen off, every new WhatsApp message goes straight to the inbox for a person, "
               "and the AI stays quiet.")
    sb.auto_reply = b.toggle("On", value=sb.auto_reply, key="auto_reply_toggle")

left, right = st.columns(2, gap="large")
with left:
    st.subheader("Salon profile")
    st.markdown(f'<div class="kv"><b>Name</b> {BUSINESS["name"]}<br><b>Address</b> {BUSINESS["address"]}<br>'
                f'<b>Time zone</b> {BUSINESS["timezone"]}<br><b>Chairs</b> {BUSINESS["chairs"]} '
                f'(the AI never books more than this at once)<br><b>Slots</b> every {BUSINESS["slot_minutes"]} minutes</div>',
                unsafe_allow_html=True)
    st.subheader("Opening hours")
    names = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}
    st.dataframe(pd.DataFrame([{"Day": names[d], "Open": h[0] if h else "Closed", "Close": h[1] if h else ""}
                               for d, h in BUSINESS["hours"].items()]), hide_index=True, width="stretch")
    st.subheader("Policies")
    st.markdown(BUSINESS["faq"])
with right:
    st.subheader("Services & prices")
    st.dataframe(pd.DataFrame([{"Service": v["label"], "Duration": f"{v['minutes']} min", "Price": v["price"], "Tool value": k}
                               for k, v in BUSINESS["services"].items()]), hide_index=True, width="stretch")
    st.subheader("Instructions the AI follows")
    st.code(SYSTEM.format(name=BUSINESS["name"], today=core.local_now().strftime("%A %d %B %Y")), language=None, wrap_lines=True)
    st.subheader("Tools the AI can call")
    st.dataframe(pd.DataFrame([{"Tool": t["function"]["name"], "What it does": t["function"]["description"]} for t in TOOL_SCHEMAS]),
                 hide_index=True, width="stretch")
    st.caption("Each tool runs against the salon's database. The customer's number comes from WhatsApp, "
               "so a customer can only see or cancel their own bookings.")

st.divider()
if st.button("Reset demo data", icon=":material/restart_alt:", help="Start again with fresh sample data"):
    core.reset()
    st.rerun()
