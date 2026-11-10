import streamlit as st

from lib import llm
from relay import core, style

sb = core.sandbox()
style.title("Send a test email", "Write to Lumen support as a customer. The email lands in the queue and the agent team handles it with a real language model.")

SAMPLES = {
    "Charged twice": ("sara@brightlane.co", "Charged twice this month??",
                      "Hi, our card was charged $588 twice on November 1st. Can you please fix this and refund the extra charge?\nThanks, Sara"),
    "SSO broken": ("marcus@tidewaterco.com", "Okta login fails",
                   "Nobody can log in with Okta since this morning, the error says SAML response signature invalid. Urgent!\nMarcus"),
    "Refund request": ("emma@sundialhr.com", "Refund for unused seats",
                       "We only use 9 of our 15 seats now. Can we get money back for the 6 unused seats this month?\nEmma"),
    "Pricing question": ("jordan@quarrybank.com", "Quote for 200 users",
                         "Hi, we have 200 analysts and need SSO, SCIM and audit logs. What would an annual plan cost?\nJordan"),
    "Something else": ("press@dailytechwire.com", "Interview request",
                       "Hi, I'm writing a story on analytics startups and would love to interview your CEO next week.\nAlex"),
}
pick = st.pills("Start from an example", list(SAMPLES), default="Charged twice")
sender, subject, body = SAMPLES.get(pick, ("", "", ""))

with st.form("compose"):
    known = {c["email"]: f"{c['name']} · {c['company']} ({c['plan']})" for c in core.CUSTOMERS}
    a, b = st.columns([1, 1])
    frm = a.text_input("From", value=sender, help="Use a customer's address so the agents can look up their account: " + ", ".join(list(known)[:3]) + "…")
    if frm.lower() in known:
        b.markdown(f"<div style='padding-top:30px;font-size:14px;opacity:.75'>Existing customer: {known[frm.lower()]}</div>", unsafe_allow_html=True)
    subj = st.text_input("Subject", value=subject)
    text = st.text_area("Message", value=body, height=170)
    run_now = st.checkbox("Run the agents straight away", value=True)
    sent = st.form_submit_button("Send to support", type="primary", icon=":material/send:")

if sent:
    if not (frm.strip() and subj.strip() and text.strip()):
        st.error("Fill in From, Subject and Message.")
        st.stop()
    t = sb.new_ticket(frm.strip(), subj.strip(), text.strip())
    if run_now:
        if not llm.groq_key():
            st.error("This deployment has no GROQ_API_KEY secret, so the agents can't run.")
            st.stop()
        try:
            with st.status(f"{t['id']} received · agents working…", expanded=True) as box:
                def step(node, update):
                    who, what = core.STEP.get(node, (node, ""))
                    extra = ""
                    if node == "supervisor":
                        extra = f": {update.get('category')}, {update.get('urgency')} urgency"
                    if node == "reviewer" and update.get("rewrites"):
                        extra = ": found a problem, sent it back to the writer"
                    st.markdown(f"**{who}** · {what}{extra}")
                sb.start(t, on_step=step)
                box.update(label=f"{t['id']} ready for review", state="complete")
        except Exception as exc:  # noqa: BLE001
            llm.friendly_error(exc)
            st.stop()
    core.open_ticket(t["id"])
