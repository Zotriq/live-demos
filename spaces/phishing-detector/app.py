import sys
from pathlib import Path

import gradio as gr

sys.path.insert(0, str(Path(__file__).parent / "project" / "code"))
sys.path.insert(0, str(Path(__file__).parent / "shared"))

from detector import check_email, check_url  # noqa: E402
import ui  # noqa: E402

URL_EXAMPLES = [
    "https://github.com/Zotriq",
    "http://paypal-secure-login.com.verify-account.ru/login?id=123",
    "http://192.168.4.20/@bank-login",
    "http://secure-update-apple.id-verify.com",
    "https://en.wikipedia.org/wiki/Phishing",
]
EMAIL_EXAMPLES = [
    "Hi team, the client call moved to 3pm tomorrow. I've updated the invite. Thanks, Sara",
    "URGENT! You have won a FREE prize worth $1000. Call now to claim your cash reward before it expires.",
    "Your account has been suspended. Reply with your password to verify your identity and restore access.",
]


def render(result) -> str:
    reasons = "".join(f"<li>{r}</li>" for r in result.reasons) or "<li>No warning signs found.</li>"
    return (
        f'<div class="verdict v-{result.verdict.lower()}"><b>{result.verdict}</b> · phishing score {result.score:.0%}'
        f'<ul style="margin:8px 0 0 18px">{reasons}</ul></div>'
    )


def url_fn(url: str) -> str:
    if not url.strip():
        return '<div class="demo-note">Paste a link first.</div>'
    return render(check_url(url))


def email_fn(text: str) -> str:
    if not text.strip():
        return '<div class="demo-note">Paste an email first.</div>'
    return render(check_email(text))


with gr.Blocks(title="AI Phishing Detector · Zohaib Tariq") as demo:
    ui.header(
        "AI Phishing Detector",
        "Two machine-learning models: one checks links for the tricks phishing sites use, "
        "the other reads an email and spots scam language. Every verdict comes with the reasons.",
        "https://github.com/Zotriq/ai-phishing-detector",
        "Nothing you paste is stored. The link checker looks at the URL text only and never opens the site.",
    )
    with gr.Tab("Check a link"):
        url = gr.Textbox(label="URL", placeholder="https://…", lines=1)
        btn = gr.Button("Check link", variant="primary")
        url_out = gr.HTML()
        gr.Examples(URL_EXAMPLES, inputs=url, label="Try one")
        btn.click(url_fn, url, url_out, api_name="check_url")
        url.submit(url_fn, url, url_out, api_name=False)
    with gr.Tab("Check an email"):
        email = gr.Textbox(label="Email text", lines=7, placeholder="Paste the email body…")
        btn2 = gr.Button("Check email", variant="primary")
        email_out = gr.HTML()
        gr.Examples(EMAIL_EXAMPLES, inputs=email, label="Try one")
        btn2.click(email_fn, email, email_out, api_name="check_email")
    gr.Markdown(
        "**How it works:** the link model is a Random Forest trained on the UCI phishing dataset, using the 10 "
        "warning signs that can be measured from a URL (90.5% accuracy on held-out data), plus rules for red flags "
        "that are dangerous on their own. The email model is a Naive Bayes classifier over word counts.",
        elem_classes="demo-note",
    )
    ui.footer()

if __name__ == "__main__":
    ui.launch(demo)
