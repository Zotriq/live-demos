import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glow import core, style  # noqa: E402

st.set_page_config(page_title="Glow Desk · WhatsApp AI receptionist", page_icon="💬", layout="wide")
style.inject()
sb = core.sandbox()
waiting = len(sb.store.waiting_for_human())

ASSETS = Path(__file__).resolve().parent / "assets"
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))

pages = {
    "Workspace": [
        st.Page("views/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
        st.Page("views/inbox.py", title="Inbox" + (f"  ·  {waiting} waiting" if waiting else ""), icon=":material/forum:", url_path="inbox"),
        st.Page("views/appointments.py", title="Appointments", icon=":material/calendar_month:", url_path="appointments"),
        st.Page("views/customers.py", title="Customers", icon=":material/group:", url_path="customers"),
        st.Page("views/analytics.py", title="Analytics", icon=":material/monitoring:", url_path="analytics"),
    ],
    "Try it": [
        st.Page("views/phone.py", title="Customer's phone", icon=":material/smartphone:", url_path="phone"),
    ],
    "Setup": [
        st.Page("views/business.py", title="Business & AI", icon=":material/storefront:", url_path="business"),
        st.Page("views/integrations.py", title="Integrations", icon=":material/hub:", url_path="integrations"),
    ],
}
nav = st.navigation(pages, position="sidebar", expanded=True)
style.sidebar()
nav.run()
