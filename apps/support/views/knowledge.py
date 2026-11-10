import streamlit as st

from relay import core, style

sb = core.sandbox()
style.title("Knowledge base", "Help-centre articles the technical agent searches, and the policies the billing and sales agents follow.")

query = st.text_input("Test a search", placeholder="e.g. names with accents look wrong after importing from Excel",
                      help="Runs the same search the technical agent uses on every email")
if query:
    hits = sb.kb.search(query)
    if hits:
        st.success("The technical agent would read: " + ", ".join(f"**{n}**" for n, _ in hits))
    else:
        st.warning("No article matches. The agent would tell the writer there is no help article for this.")

titles = {name: text.splitlines()[0].lstrip("# ").strip() for name, text in sb.kb.articles.items()}
used = {}
for t in sb.tickets.values():
    for s in t["trace"]:
        if s["node"] in ("technical", "billing", "sales") and s["text"].startswith("Sources:"):
            for src in s["text"].split("\n")[0].removeprefix("Sources:").split(","):
                used[src.strip()] = used.get(src.strip(), 0) + 1

left, right = st.columns([1, 2], gap="large")
with left:
    pick = st.radio("Articles", list(titles), format_func=lambda n: f"{titles[n]}  ·  used {used.get(n, 0)}×",
                    label_visibility="collapsed")
with right:
    with st.container(border=True):
        st.markdown(sb.kb.articles[pick])
        st.caption(f"File: data/kb/{pick}.md · cited in {used.get(pick, 0)} ticket replies")
