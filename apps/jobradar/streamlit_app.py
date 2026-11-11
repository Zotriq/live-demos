"""Job Radar - Streamlit entry point.  Run:  streamlit run app.py"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(page_title="Job Radar", page_icon=":material/radar:", layout="wide",
                   initial_sidebar_state="expanded")

from ui.common import setup, sidebar_status  # noqa: E402

setup()

nav = st.navigation({
    "Agent": [
        st.Page("views/run.py", title="Run discovery", icon=":material/play_circle:", default=True),
        st.Page("views/jobs.py", title="Jobs database", icon=":material/table_view:"),
        st.Page("views/slack.py", title="Slack alerts", icon=":material/notifications:"),
        st.Page("views/history.py", title="Run history", icon=":material/history:"),
    ],
    "System": [
        st.Page("views/architecture.py", title="Architecture", icon=":material/account_tree:"),
        st.Page("views/settings.py", title="Search profile & setup", icon=":material/tune:"),
    ],
})
sidebar_status()
nav.run()
