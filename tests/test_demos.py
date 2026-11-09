"""Click through every demo page headlessly with Streamlit's AppTest.

The AI demos make real calls to Groq, so CI runs them with the GROQ_API_KEY secret;
without it those tests are skipped. Run: pytest tests -s
"""

import os
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
needs_groq = pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="needs GROQ_API_KEY")
TIMEOUT = 240


def page(name: str) -> AppTest:
    at = AppTest.from_file(str(ROOT / "demos" / f"{name}.py"), default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, at.exception
    return at


def click(at: AppTest, label: str) -> AppTest:
    [b for b in at.button if b.label.startswith(label)][0].click().run()
    assert not at.exception, at.exception
    return at


def texts(at: AppTest) -> str:
    parts = [m.value for m in at.markdown if not str(m.value).startswith("<")] + [c.value for c in at.code]
    parts += [h.value for h in at.subheader] + [c.value for c in at.caption]
    parts += [f"{k.label}={k.value}" for k in at.metric]
    for kind in ("success", "warning", "error", "info"):
        parts += [f"[{kind}] {e.value}" for e in getattr(at, kind)]
    return "\n".join(map(str, parts))


def report(name: str, at: AppTest) -> str:
    out = texts(at)
    print(f"\n===== {name} =====\n{out[-2500:]}")
    return out


def test_home():
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    at.run()
    assert not at.exception, at.exception


def test_postgres_tuning():
    at = click(page("postgres_tuning"), "Run before")
    out = report("postgres tuning", at)
    assert "Speed-up" in out and "yes ✅" in out


def test_etl():
    at = click(page("etl"), "Run the ETL")
    out = report("etl", at)
    assert "Rejected=5" in out


def test_phishing():
    at = page("phishing")
    at.text_input[0].set_value("http://paypal-secure-login.com.verify-account.ru/login?id=123").run()
    assert "Phishing" in report("phishing", at)


def test_mcp_guard():
    at = page("mcp_server")
    click(at, "Run through the guard")
    assert "Blocked" in report("mcp guard", at)


@needs_groq
def test_mcp_ask():
    at = page("mcp_server")
    at.text_input[0].set_value("Which 5 countries brought in the most revenue from paid or shipped orders?")
    click(at, "Ask")
    out = report("mcp ask", at)
    assert "SELECT" in out.upper() and not at.error


@needs_groq
def test_invoice():
    at = click(page("invoice"), "Extract invoice")
    out = report("invoice", at)
    assert "Total=" in out and not at.error


@needs_groq
def test_support_agents():
    at = click(page("support_agents"), "Run the agents")
    out = report("support agents (draft)", at)
    assert "Waiting for your approval" in out, out
    click(at, "Approve")
    out = report("support agents (sent)", at)
    assert "Sent after human approval" in out


@needs_groq
def test_whatsapp():
    at = page("whatsapp")
    for msg in ["Hi! What services do you have and how much is a facial?",
                "Can I book a haircut tomorrow at 4pm? My name is Ali"]:
        at.chat_input[0].set_value(msg).run()
        assert not at.exception, at.exception
    chat = at.session_state["wa"]["chat"]
    print("\n===== whatsapp =====")
    for m in chat:
        print(("ME:  " if m["me"] else "BOT: ") + m["body"])
    print(report("whatsapp side panel", at)[-1200:])
    assert len([m for m in chat if not m["me"]]) == 2


@needs_groq
def test_voice_receptionist():
    at = page("voice")
    for msg in ["Hi, I'd like to book a check-up next Tuesday, what times do you have?",
                "The earliest one please. My name is Sam Lee and my number is 555 0100."]:
        at.chat_input[0].set_value(msg).run()
        assert not at.exception, at.exception
    v = at.session_state["voice"]
    print("\n===== voice =====")
    for role, text in v["transcript"]:
        print(f"{role.upper():9} {text}")
    for w in v["webhooks"]:
        print("WEBHOOK", w)
    print("AUDIO bytes:", len(v["audio"] or b""))
    click(at, "Hang up")
    print("CALLS:", v["server"].get("/calls").json())
    assert any(w[0] == "check_availability" for w in v["webhooks"])


def test_stripe():
    at = page("stripe_crm")
    click(at, "Send webhook")
    click(at, "Resend same event")
    click(at, "Send with forged signature")
    s = at.session_state["stripe"]
    for row in s["log"]:
        print(row)
    print("CALLS", [(c["service"], c["status"]) for c in s["calls"]], "EMAILS", [e["subject"] for e in s["emails"]])
    assert [r["response"][:3] for r in s["log"]] == ["200", "200", "400"]
    assert "'duplicate': True" in s["log"][1]["response"]
    assert len(s["calls"]) == 2 and len(s["emails"]) == 1


@needs_groq
def test_meeting_notes():
    at = click(page("meeting_notes"), "Run the workflow")
    out = report("meeting notes", at)
    tasks, recap = at.session_state["meeting_result"]
    print(recap["slack_text"])
    assert len(tasks) >= 3 and "Action items" in recap["slack_text"]
