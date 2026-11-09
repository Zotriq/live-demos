import streamlit as st

from lib import ui

repo = ui.project_path("ai-phishing-detector")
import sys  # noqa: E402

sys.path.insert(0, str(repo / "code"))
from detector import check_email, check_url  # noqa: E402

COLORS = {"Safe": st.success, "Suspicious": st.warning, "Phishing": st.error}
URLS = [
    "https://github.com/Zotriq",
    "http://paypal-secure-login.com.verify-account.ru/login?id=123",
    "http://192.168.4.20/@bank-login",
    "http://secure-update-apple.id-verify.com",
    "https://en.wikipedia.org/wiki/Phishing",
]
EMAILS = {
    "Normal work email": "Hi team, the client call moved to 3pm tomorrow. I've updated the invite. Thanks, Sara",
    "Prize scam": "URGENT! You have won a FREE prize worth $1000. Call now to claim your cash reward before it expires.",
    "Password phishing": "Your account has been suspended. Reply with your password to verify your identity and restore access.",
}


def show(result) -> None:
    COLORS[result.verdict](f"**{result.verdict}** · phishing score {result.score:.0%}")
    for reason in result.reasons:
        st.markdown(f"- {reason}")
    if not result.reasons:
        st.caption("No warning signs found.")


ui.header(
    "AI Phishing Detector",
    "Two machine-learning models: one checks a link for the tricks phishing sites use, the other reads an "
    "email and spots scam language. Every verdict comes with the reasons.",
    "ai-phishing-detector",
    note="Nothing you paste is stored. The link checker only looks at the URL text and never opens the site.",
)

link_tab, email_tab = st.tabs(["Check a link", "Check an email"])
with link_tab:
    pick = st.pills("Examples", URLS, key="url_pick")
    url = st.text_input("URL", value=pick or "", placeholder="https://…")
    if url.strip():
        show(check_url(url))
with email_tab:
    pick = st.pills("Examples", list(EMAILS), key="email_pick")
    text = st.text_area("Email text", value=EMAILS.get(pick, ""), height=160, placeholder="Paste the email body…")
    if st.button("Check email", type="primary") or (pick and text):
        if text.strip():
            show(check_email(text))

st.caption(
    "How it works: the link model is a Random Forest trained on the UCI phishing dataset using the 10 warning signs "
    "that can be measured from a URL (90.5% accuracy on held-out data), plus rules for red flags that are dangerous "
    "on their own. The email model is a Naive Bayes classifier over word counts."
)
ui.footer()
