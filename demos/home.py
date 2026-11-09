import streamlit as st

from lib import ui
from lib.registry import DEMOS

ui.header(
    "Live demos",
    "Working versions of the projects on my portfolio. Every page runs the real code from the project's "
    "GitHub repository: the AI demos use real language models, and the database demos run a real PostgreSQL "
    "server inside the app.",
    None,
    note="Hosted for free, so the app sleeps when nobody has used it for a while. If it was asleep, the first load takes about a minute.",
)
groups: dict[str, list] = {}
for file, title, path, icon, group in DEMOS:
    groups.setdefault(group, []).append((title, path, icon))
for group, items in groups.items():
    st.subheader(group)
    cols = st.columns(3)
    for i, (title, path, icon) in enumerate(items):
        cols[i % 3].page_link(f"{[d[0] for d in DEMOS if d[2] == path][0]}", label=title, icon=icon)
ui.footer()
