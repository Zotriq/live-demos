import streamlit as st

from radar.config import save_profile
from radar.models import Job
from radar.scoring import LLMScorer, RuleScorer
from ui.common import connections, get_store, header, profile, public

store = get_store()
prof = profile()
conn = connections()

header("Configuration", "Search profile & setup",
       "Change what the agent looks for without touching code. Each candidate or client can have their own profile.")


def lines(v):
    return "\n".join(v or [])


def parse(text):
    return [x.strip() for x in text.replace(",", "\n").splitlines() if x.strip()]


with st.form("profile"):
    st.markdown("#### Search profile")
    name = st.text_input("Profile name", prof.get("name", ""))
    c1, c2, c3 = st.columns(3)
    titles = c1.text_area("Target job titles", lines(prof.get("titles")), height=180)
    skills = c2.text_area("Key skills", lines(prof.get("skills")), height=180)
    locs = c3.text_area("Locations (add 'Remote' to accept remote)", lines(prof.get("locations")), height=180)
    c4, c5, c6 = st.columns(3)
    seniority = c4.multiselect("Seniority", ["intern", "junior", "mid", "senior", "principal"], prof.get("seniority", []))
    exclude = c5.text_input("Exclude titles containing", ", ".join(prof.get("exclude_title_terms", [])))
    threshold = c6.slider("Slack alert threshold", 40, 95, int(prof.get("alert_threshold", 70)), step=5)

    st.markdown("#### Sources")
    s1, s2, s3, s4 = st.columns(4)
    src = prof.get("sources", {})
    gh = s1.text_area("Greenhouse company handles", lines(src.get("greenhouse")), height=120)
    lv = s2.text_area("Lever company handles", lines(src.get("lever")), height=120)
    ab = s3.text_area("Ashby company handles", lines(src.get("ashby")), height=120)
    rm = s4.text_area("Remotive searches", lines((src.get("remotive") or {}).get("search")), height=120)
    if public():
        st.caption("Public demo: your changes apply to your session only.")
    st.caption("A handle is the last part of a careers URL: boards.greenhouse.io/**gitlab**, jobs.lever.co/**palantir**, jobs.ashbyhq.com/**notion**.")
    if st.form_submit_button("Save profile", type="primary"):
        prof.update(name=name, titles=parse(titles), skills=parse(skills), locations=parse(locs), seniority=seniority,
                    exclude_title_terms=parse(exclude), alert_threshold=threshold)
        prof["sources"] = {"greenhouse": parse(gh), "lever": parse(lv), "ashby": parse(ab),
                           "remotive": {"search": parse(rm), "limit": (src.get("remotive") or {}).get("limit", 40)}}
        if public():
            st.session_state.profile_override = prof
            st.toast("Profile updated for your session", icon="✅")
        else:
            save_profile(prof)
            st.toast("Profile saved", icon="✅")
        st.rerun()

st.markdown("#### Try the scorer")
t1, t2 = st.columns([2, 3], gap="large")
with t1:
    tt = st.text_input("Job title", "Senior DevOps Engineer")
    tl = st.text_input("Location", "Toronto, Ontario, Canada")
    td = st.text_area("Description", "Own our Kubernetes platform on GCP with Terraform. CI/CD with GitHub Actions. Python.", height=100)
    if st.button("Score it", icon=":material/insights:"):
        job = Job("manual", "x", "manual", tt, "Test Co", tl, "", td, remote="remote" in tl.lower())
        rule = RuleScorer(prof).score(job)
        llm = LLMScorer(prof)
        st.session_state.try_score = (rule, llm.score(job, rule) if llm.enabled and rule.score >= 0 else None)
with t2:
    res = st.session_state.get("try_score")
    if res:
        rule, ai = res
        st.metric("Rule score", rule.score)
        st.caption(rule.reason)
        if ai:
            st.metric("AI score", ai.score)
            st.caption(ai.reason)
        elif conn["llm"].enabled:
            st.warning("The AI call failed. Check the API key and model in .env.")
        else:
            st.info("Add an LLM key to .env to see the AI score next to the rule score.")

st.markdown("#### Connections")
st.markdown(
    f"- **AI scoring:** {conn['llm'].label if conn['llm'].enabled else 'not set (add GROQ_API_KEY or OPENAI_API_KEY to .env)'}\n"
    f"- **Slack:** {'webhook set, posting to ' + conn['slack'].channel if conn['slack'].live else 'not set (add SLACK_WEBHOOK_URL to .env)'}\n"
    f"- **Database:** {store.kind} ({'DATABASE_URL' if store.kind != 'SQLite' else 'data/job_radar.db'})")

with st.expander("Danger zone"):
    st.write("Clear all jobs, runs and alerts to start a fresh demo.")
    if st.button("Reset database", type="secondary", icon=":material/delete:"):
        store.reset()
        st.session_state.pop("last_result", None)
        st.toast("Database cleared", icon="🧹")
        st.rerun()
