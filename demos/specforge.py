import tempfile
import threading
from pathlib import Path

import streamlit as st

from lib import llm, ui

repo = ui.project_path("SpecForge")
from specforge.config import settings  # noqa: E402
from specforge.graph import run  # noqa: E402

LOCK = threading.Lock()  # settings (output folders) are process-wide, so one run at a time
EXAMPLES = [
    "I wanna build a wishlist for our shop's storefront: shoppers save products, stored in Postgres, Django + React app",
    "Add Stripe subscription billing to our FastAPI backend, plans stored in Postgres, customers see a billing page in Next.js",
    "I wanna build dark mode",
]
LABELS = {"feature_name": "Feature name", "description": "Description", "target_layer": "Target layer (storefront / backend / admin / file)",
          "data_source": "Data source", "user_facing": "User-facing? (yes / no)", "tech_stack": "Tech stack"}


def groq(system: str, user: str) -> str:
    from openai import OpenAI

    r = OpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL).chat.completions.create(
        model=llm.SMART, temperature=0, reasoning_effort="low",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return r.choices[0].message.content or ""


def forge(request: str, answers: dict) -> dict:
    folder = Path(st.session_state.setdefault("sf_dir", tempfile.mkdtemp(prefix="specforge-")))
    with LOCK:
        settings.plans_dir, settings.spec_dir = folder / ".claude" / "plans", folder / ".claude" / "spec"
        settings.project_overview, settings.trace_to_stdout = folder / "CLAUDE.md", False
        result = run(request, answers=answers, llm=groq)
    for key in ("plan_path", "spec_path"):
        if result.get("state") and result["state"].get(key):
            result[key.replace("_path", "")] = Path(result["state"][key]).read_text()
    return result


ui.header(
    "SpecForge",
    "A multi-agent MCP server for Claude Code that turns a one-line feature idea into an implementation plan and a "
    "spec an AI coding assistant can build from. A supervisor gathers the context (and asks you for anything "
    "missing instead of guessing), a planning agent writes the plan, and a spec writer turns it into testable requirements.",
    "SpecForge",
    flow=["One-line idea", "Supervisor: context or questions", "Plan Agent → plans/<feature>.md", "Spec Writer → spec/<feature>.md", "Traced, validated steps"],
    note="Built with Ahmed Javed. In Claude Code this runs as the MCP tool forge_spec; here the same pipeline runs in the page.",
)

def _pick():
    st.session_state.sf_request = st.session_state.sf_example or ""


st.pills("Examples", EXAMPLES, key="sf_example", on_change=_pick)
request = st.text_area("Feature request", height=80, key="sf_request")
if st.button("Forge spec", type="primary") and request.strip():
    st.session_state.sf_answers = {}
    try:
        with st.spinner("Supervisor → Plan Agent → Spec Writer…"):
            st.session_state.sf_result = forge(request, {})
    except Exception as exc:
        llm.friendly_error(exc)

res = st.session_state.get("sf_result")
if res and res["status"] == "gathering":
    st.info("The Supervisor needs a few details before planning (it never guesses):")
    with st.form("answers"):
        answers = {f: st.text_input(f"{LABELS.get(f, f)}: {q}") for f, q in res["questions"].items()}
        if st.form_submit_button("Continue", type="primary"):
            st.session_state.sf_answers.update({k: v for k, v in answers.items() if v.strip()})
            try:
                with st.spinner("Continuing the pipeline…"):
                    st.session_state.sf_result = forge(st.session_state.sf_request, st.session_state.sf_answers)
            except Exception as exc:
                llm.friendly_error(exc)
            st.rerun()
elif res and res["status"] == "error":
    st.error(f"The pipeline stopped (post-hook validation): {res['error'][:400]}")
elif res and res["status"] == "done":
    s = res["state"]
    st.success(f"Done: **{s['feature_name']}** · {s['target_layer']} · {s['tech_stack']}")
    plan_tab, spec_tab, trace_tab = st.tabs([".claude/plans/" + Path(s["plan_path"]).name,
                                             ".claude/spec/" + Path(s["spec_path"]).name, "Trace"])
    with plan_tab:
        st.markdown(res["plan"])
        st.download_button("Download plan", res["plan"], Path(s["plan_path"]).name)
    with spec_tab:
        st.markdown(res["spec"])
        st.download_button("Download spec", res["spec"], Path(s["spec_path"]).name)
    with trace_tab:
        for e in res["trace"]:
            detail = {k: v for k, v in e.items() if k not in ("ts", "event", "state_snapshot")}
            st.markdown(f"`{e['event']}` " + " · ".join(f"**{k}**: {v}" for k, v in detail.items()))
ui.footer()
