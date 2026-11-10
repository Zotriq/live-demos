import pandas as pd
import streamlit as st

from relay import core, style

sb = core.sandbox()
df = sb.frame()
style.title("Customers", "The account data the billing and sales agents read before they answer.")

rows = []
for c in core.CUSTOMERS:
    mine = df[df["sender"] == c["email"]]
    rows.append({"email": c["email"], "Company": c["company"], "Contact": c["name"], "Plan": c["plan"], "Seats": c["seats"],
                 "MRR ($)": c["mrr"], "Renews": c["renews_on"], "Status": c["status"].replace("_", " "),
                 "Tickets": len(mine), "Open": int(mine["status"].isin(["New", "Needs approval", "Escalated"]).sum())})
accts = pd.DataFrame(rows).sort_values("MRR ($)", ascending=False).reset_index(drop=True)

k = st.columns(4)
k[0].metric("Accounts", len(accts), border=True)
k[1].metric("Monthly revenue", f"${accts['MRR ($)'].sum():,.0f}", border=True)
k[2].metric("Seats", int(accts["Seats"].sum()), border=True)
k[3].metric("Past due", int((accts["Status"] == "past due").sum()), border=True)

left, right = st.columns([1.8, 1], gap="large")
with left:
    ev = st.dataframe(accts.drop(columns=["email"]), hide_index=True, width="stretch", height=480, on_select="rerun",
                      selection_mode="single-row", key="accts",
                      column_config={"MRR ($)": st.column_config.ProgressColumn(format="$%d", min_value=0, max_value=float(accts["MRR ($)"].max()))})
with right:
    row = accts.iloc[ev.selection.rows[0]] if ev.selection.rows else accts.iloc[0]
    c = core.BY_EMAIL[row["email"]]
    with st.container(border=True):
        st.markdown(f"### {style.esc(c['company'])}")
        st.markdown(f'<div class="kv"><b>Contact</b> {style.esc(c["name"])}<br><b>Email</b> {c["email"]}<br>'
                    f'<b>Plan</b> {c["plan"]} · {c["seats"]} seats<br><b>Customer since</b> {c["since"]}<br>'
                    f'<b>Renews</b> {c["renews_on"]}</div>', unsafe_allow_html=True)
    st.markdown("**Invoices**")
    inv = pd.DataFrame(c["invoices"])
    st.dataframe(inv.rename(columns={"number": "Invoice", "date": "Date", "amount": "Amount ($)", "status": "Status", "note": "Note"}),
                 hide_index=True, width="stretch")
    st.markdown("**Tickets**")
    mine = df[df["sender"] == c["email"]]
    if mine.empty:
        st.caption("No tickets")
    for r in mine.itertuples():
        a, b = st.columns([4, 1], vertical_alignment="center")
        a.markdown(f"{style.status(r.status)} {style.esc(r.subject)} <span style='opacity:.6;font-size:13px'>· {style.ago(r.received)}</span>",
                   unsafe_allow_html=True)
        if b.button("Open", key=f"c_{r.id}", width="stretch"):
            core.open_ticket(r.id)
