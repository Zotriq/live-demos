import html

import pandas as pd
import streamlit as st

from glow import core, style

sb = core.sandbox()
style.title("Customers", "Everyone who has booked or messaged the salon, built automatically from WhatsApp chats and bookings.")

df = sb.bookings()
convos = {c["phone"]: c for c in sb.conversations()}
rows = []
for phone in sorted(set(df["phone"]) | set(convos)):
    b = df[df["phone"] == phone]
    done = b[b["state"] == "Completed"]
    up = b[b["state"].isin(["Upcoming", "In progress"])]
    c = convos.get(phone)
    name = c["name"] if c else b["name"].iloc[-1]
    last = max([x for x in [c["last_at"] if c else None, done["start"].max() if not done.empty else None] if x is not None], default=None)
    rows.append({"phone": phone, "Customer": name, "WhatsApp": "+" + phone, "Visits": len(done), "Spent (Rs)": int(done["price"].sum()),
                 "Next visit": up["start"].min() if not up.empty else None,
                 "Favourite": done["label"].mode().iloc[0] if not done.empty else "–",
                 "Language": c["language"] if c else "–", "Last contact": last,
                 "Channel": "WhatsApp" if c else "Front desk only"})
people = pd.DataFrame(rows).sort_values(["Spent (Rs)", "Visits"], ascending=False).reset_index(drop=True)

k = st.columns(4)
k[0].metric("Customers", len(people), border=True)
k[1].metric("On WhatsApp", int((people["Channel"] == "WhatsApp").sum()), border=True)
k[2].metric("Returning (2+ visits)", int((people["Visits"] >= 2).sum()), border=True)
k[3].metric("Average spend", f"Rs {people.loc[people['Visits'] > 0, 'Spent (Rs)'].mean():,.0f}", border=True)

query = st.text_input("Search", placeholder="Search customers", label_visibility="collapsed")
shown = people[people["Customer"].str.contains(query, case=False) | people["WhatsApp"].str.contains(query)] if query else people
left, right = st.columns([2, 1], gap="large")
with left:
    event = st.dataframe(shown.drop(columns=["phone"]), hide_index=True, width="stretch", height=560,
                         on_select="rerun", selection_mode="single-row", key=f"cust_{query}",
                         column_config={"Next visit": st.column_config.DatetimeColumn(format="ddd D MMM, h:mm a"),
                                        "Last contact": st.column_config.DatetimeColumn(format="D MMM, h:mm a"),
                                        "Spent (Rs)": st.column_config.ProgressColumn(format="Rs %d", min_value=0,
                                                                                     max_value=int(people["Spent (Rs)"].max() or 1))})
with right:
    if shown.empty:
        st.stop()
    row = shown.iloc[event.selection.rows[0]] if event.selection.rows else shown.iloc[0]
    phone = row["phone"]
    with st.container(border=True):
        st.markdown(f"### {html.escape(row['Customer'])}")
        st.markdown(f'<div class="kv"><b>WhatsApp</b> {row["WhatsApp"]}<br><b>Visits</b> {row["Visits"]}<br>'
                    f'<b>Spent</b> Rs {row["Spent (Rs)"]:,}<br><b>Favourite</b> {row["Favourite"]}<br>'
                    f'<b>Language</b> {row["Language"]}</div>', unsafe_allow_html=True)
        if phone in convos and st.button("Open WhatsApp chat", icon=":material/forum:", width="stretch"):
            st.session_state.inbox_sel = phone
            st.switch_page("views/inbox.py")
    st.markdown("**History**")
    hist = df[df["phone"] == phone].sort_values("start", ascending=False)
    for r in hist.itertuples():
        st.markdown(f"{r.start:%d %b %Y · %-I:%M %p} · {r.label} · Rs {r.price:,} {style.pill(r.state)} {style.pill(r.source)}",
                    unsafe_allow_html=True)
    if hist.empty:
        st.caption("Has messaged, not booked yet.")
