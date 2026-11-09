import streamlit as st

from detector import check_email, check_url

ICON = {"Safe": "✅", "Suspicious": "⚠️", "Phishing": "🚨"}


def show(result):
    text = f"{ICON[result.verdict]} **{result.verdict}** (phishing score {result.score:.0%})"
    (st.success if result.verdict == "Safe" else st.warning if result.verdict == "Suspicious" else st.error)(text)
    for reason in result.reasons:
        st.write(f"- {reason}")


st.title("🔐 Phishing Detection System")
option = st.selectbox("Choose input type", ["URL", "Email"])

if option == "URL":
    url_input = st.text_input("Enter the URL:")
    if st.button("Check URL"):
        show(check_url(url_input)) if url_input else st.warning("Please enter a URL.")
else:
    email_input = st.text_area("Paste the email content:")
    if st.button("Check email"):
        show(check_email(email_input)) if email_input else st.warning("Please paste some email content.")
