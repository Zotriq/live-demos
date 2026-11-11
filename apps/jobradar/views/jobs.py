import html
import io

import pandas as pd
import streamlit as st

from ui.common import JOB_COLUMNS, SOURCE_NAMES, get_store, header, jobs_frame, pill, score_html

store = get_store()
header("Centralised database", "Jobs database",
       "One row per real job. The fingerprint (company + role + location) is the dedup key, so a job found on two sources is stored once.")

df = jobs_frame(store.all_jobs())
if df.empty:
    st.info("No jobs yet. Run the discovery agent first.", icon=":material/info:")
    st.stop()

with st.container(border=True):
    f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
    q = f1.text_input("Search", placeholder="title, company, skill...", label_visibility="collapsed")
    min_score = f2.slider("Minimum score", 0, 100, 0, step=5)
    srcs = f3.multiselect("Source", sorted(df["source_name"].unique()), placeholder="All sources")
    status = f4.selectbox("Status", ["Open jobs", "All", "Alerted", "Closed"])

view = df.copy()
if q:
    ql = q.lower()
    view = view[view.apply(lambda r: ql in f"{r['title']} {r['company']} {r['location']} {r['description']}".lower(), axis=1)]
view = view[view["score"].fillna(0) >= min_score]
if srcs:
    view = view[view["source_name"].isin(srcs)]
if status == "Open jobs":
    view = view[view["is_active"]]
elif status == "Alerted":
    view = view[view["status"] == "Alerted"]
elif status == "Closed":
    view = view[~view["is_active"]]

cols = ["score", "title", "company", "location", "salary", "score_reason", "source_name", "status", "url"]
st.caption(f"{len(view)} of {len(df)} jobs · click a row for details and change history")
sel = st.dataframe(view[cols], column_config=JOB_COLUMNS, hide_index=True, width="stretch",
                   on_select="rerun", selection_mode="single-row", height=min(520, 38 + 35 * max(len(view), 1)))

# exports
export = view[["score", "title", "company", "location", "remote", "salary", "employment_type", "department",
               "score_reason", "source_name", "seen_on", "status", "url", "first_seen_local"]].rename(columns={"first_seen_local": "first_seen", "source_name": "source"})
export["seen_on"] = export["seen_on"].map(lambda v: ", ".join(v or []))
e1, e2, _ = st.columns([1, 1, 4])
e1.download_button("Export CSV", export.to_csv(index=False).encode(), "jobs.csv", "text/csv", icon=":material/download:")
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    export.to_excel(xw, index=False, sheet_name="Jobs")
e2.download_button("Export Excel", buf.getvalue(), "jobs.xlsx", icon=":material/table:")

rows = sel.selection.rows if sel and sel.selection else []
if rows:
    job = view.iloc[rows[0]]
    full = store.job(int(job["id"]))
    st.markdown("---")
    a, b = st.columns([3, 2], gap="large")
    with a:
        st.markdown(f"### {html.escape(full['title'])}")
        meta = [full["company"], full["location"]]
        if full["salary"]:
            meta.append(full["salary"])
        if full["employment_type"]:
            meta.append(full["employment_type"])
        st.markdown(" · ".join(html.escape(str(m)) for m in meta))
        st.markdown(f"{score_html(full['score'])} &nbsp; {html.escape(full['score_reason'] or '')}", unsafe_allow_html=True)
        engine = "AI" if full["score_engine"] == "llm" else "rules"
        st.caption(f"Scored by {engine} · rule pre-score {full['rule_score']}")
        if full["matched_skills"]:
            st.markdown("".join(pill(s, "ok") for s in full["matched_skills"]), unsafe_allow_html=True)
        st.link_button("Open job posting", full["url"] or "#", icon=":material/open_in_new:")
        with st.expander("Job description", expanded=False):
            st.text(full["description"] or "No description provided.")
    with b:
        st.markdown("**Seen on**")
        st.markdown("".join(pill(f"{SOURCE_NAMES.get(s.split(':')[0], s)} · {s.split(':', 1)[1]}") for s in full["seen_on"] or []), unsafe_allow_html=True)
        st.markdown("**Fingerprint**")
        st.code(full["fingerprint"], language=None)
        st.markdown("**Change history**")
        items = []
        for h in store.history(full["id"]):
            when = pd.to_datetime(h["changed_at"], utc=True).tz_convert(None).strftime("%b %d, %H:%M")
            detail = ""
            if h["event"] == "updated" and h["changes"]:
                detail = "<br>".join(
                    "<span style='color:#64748b'>description:</span> text updated" if k == "description" else
                    f"<span style='color:#64748b'>{html.escape(k)}:</span> <s>{html.escape(str(v[0] or '-')[:70])}</s> → {html.escape(str(v[1] or '-')[:70])}"
                    for k, v in h["changes"].items())
            label = {"created": "First seen", "updated": "Changed", "closed": "Closed (no longer listed)", "reopened": "Reopened"}.get(h["event"], h["event"])
            items.append(f"<div><span class='ev'>{label}</span> <span class='when'>· run #{h['run_id']} · {when}</span><br>{detail}</div>")
        st.markdown(f"<div class='jr-hist'>{''.join(items)}</div>", unsafe_allow_html=True)
