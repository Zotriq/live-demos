from pathlib import Path

import streamlit as st

from ui.common import header

header("System design", "Architecture",
       "One clean database first; every other agent reads from and writes to it. The highlighted path is built and running in this demo.")

SVG = """
<svg viewBox="0 0 900 470" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:980px;font-family:-apple-system,Segoe UI,Inter,sans-serif">
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#94a3b8"/></marker>
<marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#2563eb"/></marker></defs>
<rect x="10" y="20" width="880" height="128" rx="12" fill="#eff6ff"/>
<text x="26" y="44" font-size="12" font-weight="700" fill="#2563eb" letter-spacing="1">BUILT IN THIS DEMO · MILESTONE 1</text>
<g font-size="14">
 <rect x="26" y="60" width="190" height="70" rx="10" fill="#fff" stroke="#2563eb" stroke-width="1.5"/><text x="121" y="90" text-anchor="middle" font-weight="700" fill="#0f172a">Job sources</text><text x="121" y="110" text-anchor="middle" font-size="12" fill="#475569">4 public job APIs</text>
 <rect x="244" y="60" width="190" height="70" rx="10" fill="#fff" stroke="#2563eb" stroke-width="1.5"/><text x="339" y="90" text-anchor="middle" font-weight="700" fill="#0f172a">Discovery agent</text><text x="339" y="110" text-anchor="middle" font-size="12" fill="#475569">fetch · normalise · schedule</text>
 <rect x="462" y="60" width="190" height="70" rx="10" fill="#fff" stroke="#2563eb" stroke-width="1.5"/><text x="557" y="90" text-anchor="middle" font-weight="700" fill="#0f172a">Dedup + scoring</text><text x="557" y="110" text-anchor="middle" font-size="12" fill="#475569">fingerprint · rules → LLM</text>
 <rect x="680" y="60" width="194" height="70" rx="10" fill="#fff" stroke="#2563eb" stroke-width="1.5"/><text x="777" y="90" text-anchor="middle" font-weight="700" fill="#0f172a">Notification agent</text><text x="777" y="110" text-anchor="middle" font-size="12" fill="#475569">Slack alerts · run summary</text>
</g>
<g stroke="#2563eb" stroke-width="1.5" fill="none"><path d="M216 95H242" marker-end="url(#b)"/><path d="M434 95H460" marker-end="url(#b)"/><path d="M652 95H678" marker-end="url(#b)"/><path d="M557 130V186" marker-end="url(#b)"/></g>
<rect x="300" y="188" width="300" height="70" rx="10" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
<text x="450" y="218" text-anchor="middle" font-size="15" font-weight="700" fill="#0f172a">PostgreSQL / Supabase</text>
<text x="450" y="238" text-anchor="middle" font-size="12" fill="#334155">jobs · history · runs · alerts (+ candidates, leads)</text>
<g stroke="#94a3b8" stroke-width="1.3" fill="none"><path d="M450 258V290"/><path d="M118 290H782"/><path d="M118 290V316" marker-end="url(#a)"/><path d="M340 290V316" marker-end="url(#a)"/><path d="M560 290V316" marker-end="url(#a)"/><path d="M782 290V316" marker-end="url(#a)"/></g>
<text x="460" y="282" font-size="11" fill="#64748b">read and write</text>
<g font-size="13">
 <rect x="26" y="318" width="184" height="62" rx="10" fill="#fff" stroke="#cbd5e1" stroke-dasharray="5 4"/><text x="118" y="344" text-anchor="middle" font-weight="700" fill="#0f172a">Job Matching</text><text x="118" y="363" text-anchor="middle" font-size="11.5" fill="#64748b">candidate fit scores</text>
 <rect x="248" y="318" width="184" height="62" rx="10" fill="#fff" stroke="#cbd5e1" stroke-dasharray="5 4"/><text x="340" y="344" text-anchor="middle" font-weight="700" fill="#0f172a">Recruiter Research</text><text x="340" y="363" text-anchor="middle" font-size="11.5" fill="#64748b">licensed contact data</text>
 <rect x="468" y="318" width="184" height="62" rx="10" fill="#fff" stroke="#cbd5e1" stroke-dasharray="5 4"/><text x="560" y="344" text-anchor="middle" font-weight="700" fill="#0f172a">Application Assistant</text><text x="560" y="363" text-anchor="middle" font-size="11.5" fill="#64748b">drafts · human approval</text>
 <rect x="690" y="318" width="184" height="62" rx="10" fill="#fff" stroke="#cbd5e1" stroke-dasharray="5 4"/><text x="782" y="344" text-anchor="middle" font-weight="700" fill="#0f172a">Reporting</text><text x="782" y="363" text-anchor="middle" font-size="11.5" fill="#64748b">daily · weekly · exports</text>
</g>
<rect x="26" y="404" width="848" height="48" rx="10" fill="#f8fafc" stroke="#e2e8f0"/>
<text x="450" y="433" text-anchor="middle" font-size="13" fill="#334155">Runs on a schedule in the cloud (GCP Cloud Run Jobs or AWS ECS) · logs · retries · failure alerts to Slack</text>
</svg>
"""
st.markdown(SVG, unsafe_allow_html=True)
st.caption("Solid blue = working now. Dashed = next milestones, each reading the same database.")

c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown("#### How a run works")
    st.markdown(
        "1. **Fetch** every configured board or search. A failing board is logged and skipped, never stops the run.\n"
        "2. **Normalise** each posting to one shape: title, company, location, salary, link, description, date.\n"
        "3. **Fingerprint** = company + role + primary location. Same fingerprint = same real job, even across sources.\n"
        "4. **Change detection**: a content hash per posting; changes to salary, title, location or text are saved as history. Jobs no longer listed are marked closed, never deleted.\n"
        "5. **Score**: free rules filter clear misses; only promising jobs go to the LLM for a 0-100 score with a reason.\n"
        "6. **Alert**: jobs at or above the threshold post to Slack once; each run posts a summary.")
with c2:
    st.markdown("#### Compliant sources only")
    st.markdown(
        "| Source | What it is | Access |\n|---|---|---|\n"
        "| Greenhouse | Company career pages | Public Job Board API |\n"
        "| Lever | Company career pages | Public Postings API |\n"
        "| Ashby | Company career pages | Public Posting API |\n"
        "| Remotive | Remote job board | Public API, credited, max ~4 calls/day |\n"
        "| LinkedIn, Indeed | Big boards | No open job API; use licensed aggregators instead |")

with st.expander("Database schema (PostgreSQL / Supabase)"):
    st.code((Path(__file__).resolve().parent.parent / "sql" / "schema.sql").read_text(), language="sql")
