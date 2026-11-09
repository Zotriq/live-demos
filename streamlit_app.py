"""All live demos in one Streamlit app. Each demo is its own page with its own URL."""

import streamlit as st

from lib.registry import DEMOS


st.set_page_config(page_title="Live demos · Zohaib Tariq", page_icon="⚙️", layout="wide")

home = st.Page("demos/home.py", title="All demos", icon=":material/home:", default=True)
groups: dict[str, list] = {"": [home]}
for file, title, path, icon, group in DEMOS:
    groups.setdefault(group, []).append(st.Page(file, title=title, url_path=path, icon=icon))

st.navigation(groups, position="sidebar", expanded=True).run()
