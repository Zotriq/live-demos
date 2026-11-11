import sys
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))
from ops import core, style  # noqa: E402

st.set_page_config(page_title="Operator OS · AI growth operator workspace", page_icon="🧭", layout="wide")
style.inject()
st.logo(str(APP / "assets" / "logo.svg"), size="large", icon_image=str(APP / "assets" / "icon.svg"))
core.ws()

pages = {
    "Run the business": [
        st.Page("views/command.py", title="Command centre", icon=":material/dashboard:", default=True),
        st.Page("views/pipeline.py", title="Sales pipeline", icon=":material/view_kanban:", url_path="pipeline"),
        st.Page("views/team.py", title="Team & tasks", icon=":material/groups:", url_path="team"),
    ],
    "AI tools that sell": [
        st.Page("views/leaddesk.py", title="Lead Desk (HVAC)", icon=":material/sms:", url_path="lead-desk"),
        st.Page("views/demos.py", title="Demo Generator", icon=":material/auto_awesome:", url_path="demo-generator"),
        st.Page("views/twin.py", title="AI Twin Studio", icon=":material/record_voice_over:", url_path="ai-twin"),
        st.Page("views/content.py", title="Content Engine", icon=":material/campaign:", url_path="content"),
    ],
    "About": [
        st.Page("views/about.py", title="How it fits together", icon=":material/hub:", url_path="how-it-works"),
    ],
}
nav = st.navigation(pages, position="sidebar", expanded=True)
style.sidebar()
nav.run()
