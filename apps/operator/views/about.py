import streamlit as st

from ops import style

style.title("How it fits together", "Seven income streams are too many to run separately. Operator OS groups them into three businesses "
            "that share one CRM, one sales process and one team.")

st.graphviz_chart("""
digraph {
  rankdir=LR; bgcolor="transparent"; node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=11 color="#e2d6c6" fillcolor="#ffffff"];
  edge [color="#b7a690" fontname="Helvetica" fontsize=9];
  subgraph cluster_a { label="Agency (the money)"; fontname="Helvetica"; color="#f3c4a8"; style="rounded";
    retain [label="Agency retainers\\n(CRM + AI follow-up)" fillcolor="#fde8dc"]; hvac [label="HVAC outreach"]; events [label="Events consulting"]; twin [label="AI Twin offer"]; }
  subgraph cluster_l { label="Lead source"; fontname="Helvetica"; color="#c3d3f2"; style="rounded"; yt [label="YouTube channel" fillcolor="#e6eefc"]; }
  subgraph cluster_b { label="Background income"; fontname="Helvetica"; color="#c4e2cc"; style="rounded"; music [label="AI Music" fillcolor="#e7f3e9"]; books [label="AI Books" fillcolor="#e7f3e9"]; }
  demo [label="Demo Generator" shape=ellipse fillcolor="#fff6ee"]; desk [label="Lead Desk" shape=ellipse fillcolor="#fff6ee"];
  studio [label="AI Twin Studio" shape=ellipse fillcolor="#fff6ee"]; engine [label="Content Engine" shape=ellipse fillcolor="#fff6ee"];
  crm [label="One pipeline + weekly brief\\n(Command centre)" fillcolor="#1f1b16" fontcolor="#ffffff"];
  demo -> hvac; demo -> events; hvac -> retain [label="sell"]; events -> retain; desk -> retain [label="deliver"];
  yt -> twin [label="coaches"]; studio -> twin; engine -> yt; engine -> music; engine -> books;
  retain -> crm; twin -> crm; music -> crm; books -> crm;
}
""", width="stretch")

a, b, c = st.columns(3, gap="large")
a.markdown("### Agency\nGHL retainers, HVAC outreach, events consulting and the AI Twin offer all sell AI services to small businesses, "
           "so they share one offer ladder and one pipeline. **Demo Generator** opens doors; **Lead Desk** and **AI Twin Studio** are "
           "what clients pay for every month.")
b.markdown("### Lead source\nThe YouTube channel speaks to coaches and consultants, the ideal buyers for an AI twin. The **Content Engine** "
           "turns each video into Shorts and posts, so one recording feeds the whole week.")
c.markdown("### Background income\nAI music and books grow slowly. They get one fixed weekly routine from the **Content Engine**, run by "
           "their contractors, so they stop taking the founder's attention.")

st.subheader("The operator's week")
st.markdown("""
| When | What happens | Who |
| --- | --- | --- |
| Monday | AI writes the founder's brief; 10-minute check-in on decisions | Operator + AI |
| Daily | Lead Desk answers new leads in seconds; operator follows up on demo replies | AI agent + Operator |
| Tue to Thu | 25 personalised demos sent; discovery calls booked and run | AI agent + Operator |
| Weekly | Content Engine drafts the week; contractors check and schedule | AI agent + Contractors |
| Friday | Pipeline review, client reports sent automatically | Automation + Operator |
""")
st.caption("Built with Python, Streamlit and open-weight language models served by Groq (tool calling for the Lead Desk, JSON output for demos, "
           "speech for the AI twin). In production it connects to GoHighLevel through webhooks and its API.")
