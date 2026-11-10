import streamlit as st

from relay import core, style

sb = core.sandbox()
df = sb.frame()
style.title("Tickets", "Every support email. Click a ticket to see what each agent did and to approve the reply.")

a, b, c = st.columns([4, 2, 2])
view = a.segmented_control("Status", ["Open", "To approve", "New", "Escalated", "Closed", "All"], default="Open",
                           label_visibility="collapsed") or "Open"
cats = b.multiselect("Category", ["billing", "technical", "sales", "other"], placeholder="All categories", label_visibility="collapsed")
query = c.text_input("Search", placeholder="Search subject, customer or ID", label_visibility="collapsed")

groups = {"Open": ["New", "Needs approval", "Escalated"], "To approve": ["Needs approval"], "Closed": ["Sent", "Rejected", "Resolved by staff"]}
shown = df[df["status"].isin(groups.get(view, [view] if view != "All" else core.STATUSES))]
if cats:
    shown = shown[shown["category"].isin(cats)]
if query:
    q = query.lower()
    shown = shown[shown.apply(lambda r: q in f"{r['id']} {r['subject']} {r['name']} {r['company']}".lower(), axis=1)]

st.caption(f"{len(shown)} ticket{'s' if len(shown) != 1 else ''} · click a row to open it")
table = shown.assign(
    Status=shown["status"].map(lambda s: f"{style.STATUS_ICON.get(s, '')} {s}"),
    Received=shown["received"].map(style.ago),
)[["id", "Status", "subject", "name", "company", "category", "urgency", "Received", "assignee"]].rename(columns={
    "id": "Ticket", "subject": "Subject", "name": "Customer", "company": "Company", "category": "Category",
    "urgency": "Urgency", "assignee": "Handled by"})
event = st.dataframe(table, hide_index=True, width="stretch", height=min(38 + 35 * (len(table) + 1), 720), on_select="rerun",
                     selection_mode="single-row", key=f"tickets_{view}_{cats}_{query}_{st.session_state.get('tk_n', 0)}",
                     column_config={"Subject": st.column_config.TextColumn(width="medium")})
if event.selection.rows:
    st.session_state.tk_n = st.session_state.get("tk_n", 0) + 1
    core.open_ticket(shown.iloc[event.selection.rows[0]]["id"])
