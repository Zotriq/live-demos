import asyncio
import sys

import pandas as pd
import streamlit as st
from openai import AsyncOpenAI

from lib import llm, ui

repo = ui.project_path("ai-lead-qualification-agent")
sys.path.insert(0, str(repo / "backend"))
from app.services.ai_lead_analyzer import AILeadAnalyzer  # noqa: E402
from app.services.email_generator import EmailGenerator  # noqa: E402
from app.services.scoring_engine import ScoringEngine  # noqa: E402

LEADS = {
    "COO, big budget, urgent": dict(
        name="Marcus Rivera", email="m.rivera@enterprise-global.com", company="Enterprise Global Inc.",
        job_title="Chief Operating Officer", company_size=850, budget=60000, timeline="this_month", industry="Logistics",
        country="United States", phone="+1 212 555 0344",
        message="We process 4,000 shipping documents a week by hand and need an AI pipeline to extract and route them. "
                "Board approved budget this quarter; we want to start in the next 2-3 weeks."),
    "Small agency, exploring": dict(
        name="Hina Qureshi", email="hina@pixelnest.studio", company="PixelNest Studio", job_title="Project Manager",
        company_size=12, budget=3000, timeline="3_months", industry="Marketing", country="Pakistan", phone="",
        message="Curious whether a chatbot could answer client questions about our packages. Just exploring options for now."),
    "Spam": dict(
        name="Best SEO", email="seo-offer@freemail.biz", company="", job_title="", company_size=None, budget="",
        timeline="", industry="", country="", phone="",
        message="CHEAP SEO!!! Get 10000 backlinks now, guaranteed first page google, click here limited offer"),
}
COLOR = {"hot": "🔥", "warm": "🌤️", "cold": "❄️", "unqualified": "🚫"}

ui.header(
    "AI Lead Qualification Agent",
    "Scores every inbound lead twice: a transparent rules engine (budget, timeline, seniority, intent, spam signals) "
    "and an AI analysis. The scores are blended, the lead is classed hot / warm / cold, and a personalised follow-up "
    "email is drafted for a human to approve before anything is sent or synced to the CRM.",
    "ai-lead-qualification-agent",
    flow=["Lead arrives (form, CRM, n8n)", "Rules engine score", "AI analysis", "60% AI + 40% rules", "Draft follow-up → approve → CRM + Slack"],
)

pick = st.pills("Sample leads", list(LEADS), default=list(LEADS)[0])
base = LEADS.get(pick, LEADS[list(LEADS)[0]])
with st.form("lead"):
    c1, c2, c3 = st.columns(3)
    lead = {
        "name": c1.text_input("Name", base["name"]), "email": c2.text_input("Email", base["email"]),
        "company": c3.text_input("Company", base["company"]), "job_title": c1.text_input("Job title", base["job_title"]),
        "company_size": c2.text_input("Company size (people)", str(base["company_size"] or "")),
        "budget": c3.text_input("Budget (USD)", str(base["budget"])), "timeline": c1.selectbox(
            "Timeline", ["asap", "this_month", "3_months", "6_months", "exploring", ""],
            index=["asap", "this_month", "3_months", "6_months", "exploring", ""].index(base["timeline"])),
        "industry": c2.text_input("Industry", base["industry"]), "country": c3.text_input("Country", base["country"]),
        "phone": base["phone"], "message": st.text_area("Message", base["message"], height=90),
    }
    go = st.form_submit_button("Qualify this lead", type="primary")

if go:
    lead["company_size"] = int(lead["company_size"]) if str(lead["company_size"]).isdigit() else None
    rules = ScoringEngine().score_lead(lead)
    analyzer = AILeadAnalyzer(api_key=llm.require_key(), model=llm.SMART)
    analyzer._client = AsyncOpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL)
    with st.spinner("Rules engine done; AI is analysing the lead…"):
        ai = asyncio.run(analyzer.analyze_lead(lead, rules["score"]))
    email = EmailGenerator().generate_follow_up_email(lead, ai)
    st.session_state.lead_result = (lead, rules, ai, email)

if st.session_state.get("lead_result"):
    lead, rules, ai, email = st.session_state.lead_result
    status = ai.get("qualification_status", rules["qualification_status"])
    a, b, c, d = st.columns(4)
    a.metric("Rules score", rules["score"])
    b.metric("AI score", ai["ai_score"])
    c.metric("Final (60/40 blend)", ai["final_score"])
    d.metric("Status", f"{COLOR.get(status, '')} {status}")
    if not ai.get("ai_available"):
        st.warning("The AI call failed, so the agent fell back to the rules score (that's built in).")
    left, right = st.columns(2)
    with left:
        st.markdown("**Rules engine breakdown**")
        st.bar_chart(pd.Series({k: v for k, v in rules["breakdown"].items() if k not in ("total_before_clamp", "final_score")}, name="points"), horizontal=True, height=300)
    with right:
        st.markdown("**AI analysis**")
        st.markdown(
            f"- **Intent:** {ai.get('intent_level')} · **Budget fit:** {ai.get('budget_fit')} · **Urgency:** {ai.get('urgency')}\n"
            f"- **Decision maker:** {ai.get('decision_maker_likelihood')} · **Industry fit:** {ai.get('industry_fit')}\n"
            f"- **Next action:** {ai.get('recommended_next_action')}\n"
            f"- **Why:** {ai.get('reasoning')}")
        if ai.get("risks_or_missing_info"):
            st.markdown("**Missing / risks:** " + "; ".join(map(str, ai["risks_or_missing_info"])))
    st.markdown("**Follow-up email draft** (waits for a human to approve)")
    subject = st.text_input("Subject", email["subject"])
    body = st.text_area("Body", email["body"], height=200)
    if st.button("Approve & send"):
        st.success(f"Approved. In production this sends the email to {lead['email']}, upserts the lead in HubSpot/Airtable "
                   f"with score {ai['final_score']} ({status})" + (", and alerts #sales in Slack." if status == "hot" else "."))
ui.footer()
