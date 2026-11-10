"""All live demos in one Streamlit app. Each demo is its own page with its own URL."""

import streamlit as st

import importlib

import lib.registry

# Reload the page list each run so new demos appear after a git push without a server restart.
DEMOS = importlib.reload(lib.registry).DEMOS


st.set_page_config(page_title="Live demos · Zohaib Tariq", page_icon="⚙️", layout="wide")

home = st.Page("demos/home.py", title="All demos", icon=":material/home:", default=True)
groups: dict[str, list] = {"": [home]}
for file, title, path, icon, group in DEMOS:
    groups.setdefault(group, []).append(st.Page(file, title=title, url_path=path, icon=icon))

st.navigation(groups, position="sidebar", expanded=True).run()
