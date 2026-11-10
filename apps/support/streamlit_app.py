import sys
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))
from relay import core, style  # noqa: E402

st.set_page_config(page_title="Relay · AI support desk", page_icon="📨", layout="wide")
style.inject()
st.logo(str(APP / "assets" / "logo.svg"), size="large", icon_image=str(APP / "assets" / "icon.svg"))
sb = core.sandbox()
df = sb.frame()
waiting = int((df["status"] == "Needs approval").sum())
new = int((df["status"] == "New").sum())

pages = {
    "Support": [
        st.Page("views/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
        st.Page("views/tickets.py", title="Tickets" + (f"  ·  {new} new" if new else ""), icon=":material/inbox:", url_path="tickets"),
        st.Page("views/approvals.py", title="Approvals" + (f"  ·  {waiting}" if waiting else ""), icon=":material/task_alt:", url_path="approvals"),
        st.Page("views/ticket.py", title="Ticket", icon=":material/mail:", url_path="ticket", visibility="hidden"),
        st.Page("views/customers.py", title="Customers", icon=":material/apartment:", url_path="customers"),
        st.Page("views/knowledge.py", title="Knowledge base", icon=":material/menu_book:", url_path="knowledge"),
        st.Page("views/analytics.py", title="Analytics", icon=":material/monitoring:", url_path="analytics"),
    ],
    "Try it": [
        st.Page("views/compose.py", title="Send a test email", icon=":material/edit_square:", url_path="compose"),
    ],
    "Setup": [
        st.Page("views/agents.py", title="Agents & rules", icon=":material/account_tree:", url_path="agents"),
    ],
}
nav = st.navigation(pages, position="sidebar", expanded=True)
style.sidebar()
nav.run()
