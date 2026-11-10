import datetime as dt
import html
import math

import streamlit as st

from glow import core, style

sb = core.sandbox()
salon = sb.salon
now = core.local_now()
today = now.date()
style.title("Appointments", "The salon's appointment book. The AI books into this same calendar, so it never double-books a chair.")

days = [today + dt.timedelta(days=i) for i in range(-1, 7)]
day = st.segmented_control("Day", days, default=today, format_func=lambda d: "Today" if d == today else d.strftime("%a %d"),
                           label_visibility="collapsed") or today
df = sb.bookings()
day_df = df[(df["start"].dt.date == day) & (df["state"] != "Cancelled")].sort_values("start")
hours = salon._hours(day)

k = st.columns(4)
k[0].metric("Appointments", len(day_df), border=True)
k[1].metric("Booked by the AI", int((day_df["source"] == "AI agent").sum()), border=True)
k[2].metric("Expected revenue", f"Rs {day_df['price'].sum():,.0f}", border=True)
if hours:
    open_min = (hours[1] - hours[0]).total_seconds() / 60 * core.BUSINESS["chairs"]
    used = sum((r.end - r.start).total_seconds() / 60 for r in day_df.itertuples())
    k[3].metric("Chairs booked", f"{used / open_min:.0%}", border=True)
else:
    k[3].metric("Chairs booked", "Closed", border=True)

grid_col, side = st.columns([2.2, 1], gap="large")
with grid_col:
    if not hours:
        st.info(f"The salon is closed on {day:%A}s.")
    else:
        # Give each appointment a chair: first chair that is free at its start time.
        chairs: list[list] = [[] for _ in range(core.BUSINESS["chairs"])]
        for r in day_df.itertuples():
            for c in chairs:
                if all(r.start >= o.end or r.end <= o.start for o in c):
                    c.append(r)
                    break
        step = dt.timedelta(minutes=30)
        slots = []
        t = hours[0]
        while t < hours[1]:
            slots.append(t)
            t += step
        covered = [set() for _ in chairs]
        rows = []
        for i, t in enumerate(slots):
            line = f'<td class="time">{t:%-I:%M %p}</td>'
            for ci, c in enumerate(chairs):
                if i in covered[ci]:
                    continue
                b = next((r for r in c if r.start == t), None)
                if b is None:
                    line += "<td></td>"
                    continue
                span = max(1, math.ceil((b.end - b.start) / step))
                covered[ci].update(range(i, i + span))
                past = " past" if b.end <= now else ""
                extra = f"<br>{style.pill(b.source)}" if span > 2 else ""
                line += (f'<td rowspan="{span}"><div class="slot svc-{b.service}{past}" style="height:{span * 36 - 8}px">'
                         f'<b>{html.escape(b.name)}</b>{b.label} · {b.start:%-I:%M}–{b.end:%-I:%M %p}{extra}</div></td>')
            rows.append(f"<tr>{line}</tr>")
        head = "".join(f"<th>Chair {i + 1}</th>" for i in range(len(chairs)))
        st.markdown(f'<table class="grid"><tr><th></th>{head}</tr>{"".join(rows)}</table>', unsafe_allow_html=True)

with side:
    tab_new, tab_cancel = st.tabs(["New booking", "Cancel"])
    with tab_new:
        if not hours:
            st.caption("Closed this day. Pick another day above.")
        else:
            service = st.selectbox("Service", list(core.SERVICES), format_func=lambda s: f"{core.SERVICES[s]['label']} · {core.SERVICES[s]['price']}")
            free = salon.free_times(service, day)
            if not free:
                st.warning("No free chair for this service on this day.")
            else:
                with st.form("new_booking", border=False):
                    when = st.selectbox(f"Free times ({len(free)})", free, format_func=lambda t: t.strftime("%-I:%M %p"))
                    name = st.text_input("Customer name", "Walk-in customer")
                    phone = st.text_input("WhatsApp number", "923331234567")
                    notify = st.checkbox("Send a WhatsApp confirmation", value=True)
                    if st.form_submit_button("Book", type="primary", width="stretch"):
                        code = sb.book_manually("".join(ch for ch in phone if ch.isdigit()), name.strip() or "Walk-in customer",
                                                service, dt.datetime.combine(day, when), notify)
                        st.toast(f"Booked · code {code}")
                        st.rerun()
    with tab_cancel:
        upcoming = df[df["state"] == "Upcoming"]
        if upcoming.empty:
            st.caption("Nothing to cancel.")
        else:
            code = st.selectbox("Appointment", upcoming["code"].tolist(),
                                format_func=lambda c: (lambda r: f"{r['start']:%a %d %b %-I:%M %p} · {r['name']} · {r['label']}")(
                                    upcoming[upcoming["code"] == c].iloc[0]))
            if st.button("Cancel appointment", width="stretch"):
                sb.cancel(code)
                st.toast(f"Cancelled {code}")
                st.rerun()

st.subheader("All appointments")
f1, f2 = st.columns(2)
states = f1.multiselect("Status", ["Upcoming", "In progress", "Completed", "Cancelled"], default=["Upcoming", "In progress"])
sources = f2.multiselect("Booked by", ["AI agent", "Front desk", "Phone call"], default=["AI agent", "Front desk", "Phone call"])
table = df[df["state"].isin(states) & df["source"].isin(sources)]
st.dataframe(
    table[["start", "name", "label", "price", "source", "state", "code", "phone"]].rename(columns={
        "start": "When", "name": "Customer", "label": "Service", "price": "Price (Rs)", "source": "Booked by",
        "state": "Status", "code": "Code", "phone": "WhatsApp"}),
    hide_index=True, width="stretch",
    column_config={"When": st.column_config.DatetimeColumn(format="ddd D MMM, h:mm a"),
                   "Price (Rs)": st.column_config.NumberColumn(format="%d")})
