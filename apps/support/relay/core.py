"""Relay: a helpdesk for Lumen Analytics, run by the langgraph-support-agents project.

Every ticket is a real LangGraph thread. The sample history was produced by running the same graph with
pre-written model answers; new tickets run on a real language model."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lib import llm, ui  # noqa: E402

ui.project_path("langgraph-support-agents")
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.types import Command  # noqa: E402
from support_agents.graph import build_graph  # noqa: E402
from support_agents.llm import OpenAICompatibleLLM  # noqa: E402
from support_agents.tools import CustomerDB, Email, KnowledgeBase  # noqa: E402

DATA = APP / "data"
REPO = "https://github.com/Zotriq/langgraph-support-agents"
CUSTOMERS = json.loads((DATA / "customers.json").read_text())["customers"]
BY_EMAIL = {c["email"]: c for c in CUSTOMERS}

STEP = {
    "supervisor": ("Supervisor", "Classified the email and picked a specialist"),
    "billing": ("Billing agent", "Checked the customer record and billing policy"),
    "technical": ("Technical agent", "Searched the help centre"),
    "sales": ("Sales agent", "Checked pricing and the account"),
    "escalate": ("Escalated", "Outside the agents' scope: routed to a person"),
    "writer": ("Writer", "Drafted a reply"),
    "reviewer": ("QA reviewer", "Checked the draft against the facts"),
    "human_approval": ("Waiting for approval", ""),
    "send": ("Sent", "Reply emailed to the customer"),
    "discard": ("Rejected", "Draft discarded"),
}
STATUSES = ["New", "Needs approval", "Escalated", "Sent", "Rejected", "Resolved by staff"]


def now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


class SwitchLLM:
    """Plays back scripted answers while the sample history is generated; otherwise calls the real model."""

    def __init__(self):
        self.script: list[str] | None = None
        self.real = None

    def chat(self, system: str, user: str) -> str:
        if self.script is not None:
            return self.script.pop(0)
        if self.real is None:
            self.real = OpenAICompatibleLLM(llm.groq_key(), llm.SMART, llm.GROQ_BASE_URL)
        return self.real.chat(system, user)


def describe(node: str, update: dict) -> str:
    if node == "supervisor":
        return f"Category **{update.get('category')}** · urgency **{update.get('urgency')}**\n\n{update.get('summary', '')}"
    if node in ("billing", "technical", "sales"):
        return f"Sources: {', '.join(update.get('sources', [])) or 'none found'}\n\n{update.get('notes', '')}"
    if node == "writer":
        return update.get("draft", "")
    if node == "reviewer":
        problems = update.get("review_feedback") or []
        if update.get("rewrites"):
            return "Sent back to the writer:\n- " + "\n- ".join(problems)
        return "Approved for human review." + (" Notes: " + "; ".join(problems) if problems else "")
    if node == "escalate":
        return update.get("notes", "")
    return ""


class Sandbox:
    def __init__(self):
        self.llm = SwitchLLM()
        self.outbox: list[dict] = []
        self.graph = build_graph(self.llm, customers=CustomerDB(DATA / "customers.json"), kb=KnowledgeBase(DATA / "kb"),
                                 outbox=self.outbox, checkpointer=InMemorySaver())
        self.kb = KnowledgeBase(DATA / "kb")
        self.tickets: dict[str, dict] = {}
        self.next_id = 1041
        self.selected: str | None = None
        from . import seed

        seed.populate(self)

    # ---- tickets ----
    def new_ticket(self, sender: str, subject: str, body: str, received: dt.datetime | None = None) -> dict:
        tid = f"LUM-{self.next_id}"
        self.next_id += 1
        c = BY_EMAIL.get(sender.lower())
        t = {"id": tid, "sender": sender.lower(), "name": c["name"] if c else sender.split("@")[0].title(),
             "company": c["company"] if c else sender.split("@")[-1], "subject": subject, "body": body,
             "received": received or now(), "trace": [], "drafted_at": None, "decided_at": None, "decision": None,
             "staff_reply": None, "assignee": None}
        self.tickets[tid] = t
        return t

    def config(self, t: dict) -> dict:
        return {"configurable": {"thread_id": t["id"]}}

    def state(self, t: dict):
        return self.graph.get_state(self.config(t))

    def raw(self, t: dict) -> str:
        return f"From: {t['sender']}\nSubject: {t['subject']}\n\n{t['body']}"

    def run(self, t: dict, payload, at: dt.datetime | None = None, on_step=None) -> None:
        clock = at
        for chunk in self.graph.stream(payload, self.config(t), stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__" or not isinstance(update, dict):
                    continue
                if clock is not None:
                    clock += dt.timedelta(seconds=4 + len(t["trace"]) * 3)
                stamp = clock or now()
                t["trace"].append({"node": node, "text": describe(node, update), "at": stamp,
                                   "rewrite": node == "reviewer" and bool(update.get("rewrites"))})
                if node == "reviewer" and not update.get("rewrites"):
                    t["drafted_at"] = stamp
                if node == "escalate":
                    t["drafted_at"] = stamp
                if on_step:
                    on_step(node, update)

    def start(self, t: dict, on_step=None, at: dt.datetime | None = None) -> None:
        self.run(t, {"raw_email": self.raw(t)}, at=at, on_step=on_step)

    def decide(self, t: dict, action: str, text: str | None = None, at: dt.datetime | None = None, by: str = "You") -> None:
        resume = {"action": action} if action != "edit" else {"action": "edit", "text": text}
        self.run(t, Command(resume=resume), at=at)
        t["decided_at"] = at or now()
        t["decision"] = {"approve": "Approved as written", "edit": "Edited, then sent", "reject": "Rejected"}[action]
        t["assignee"] = by

    def staff_answer(self, t: dict, text: str, by: str = "You", at: dt.datetime | None = None) -> None:
        t["staff_reply"] = text
        t["decided_at"] = at or now()
        t["decision"] = "Answered by staff"
        t["assignee"] = by
        self.outbox.append({"to": t["sender"], "subject": f"Re: {t['subject']}", "body": text})

    def status(self, t: dict) -> str:
        s = self.state(t)
        if not s.values:
            return "New"
        if any(i for task in s.tasks for i in task.interrupts):
            return "Needs approval"
        outcome = s.values.get("outcome")
        if outcome == "sent":
            return "Sent"
        if outcome == "discarded":
            return "Rejected"
        if outcome == "escalated":
            return "Resolved by staff" if t["staff_reply"] else "Escalated"
        return "New"

    def pending(self, t: dict) -> dict | None:
        s = self.state(t)
        for task in s.tasks:
            for i in task.interrupts:
                return i.value
        return None

    def frame(self) -> pd.DataFrame:
        rows = []
        for t in self.tickets.values():
            v = self.state(t).values
            rows.append({"id": t["id"], "received": t["received"], "name": t["name"], "company": t["company"],
                         "sender": t["sender"], "subject": t["subject"], "category": v.get("category", "–"),
                         "urgency": v.get("urgency", "–"), "status": self.status(t), "decision": t["decision"],
                         "rewrites": v.get("rewrites", 0) or 0, "drafted_at": t["drafted_at"], "decided_at": t["decided_at"],
                         "assignee": t["assignee"] or ("AI agents" if v else "Unassigned")})
        df = pd.DataFrame(rows)
        df["draft_secs"] = (pd.to_datetime(df["drafted_at"]) - pd.to_datetime(df["received"])).dt.total_seconds()
        df["resolve_mins"] = (pd.to_datetime(df["decided_at"]) - pd.to_datetime(df["received"])).dt.total_seconds() / 60
        return df.sort_values("received", ascending=False)


def sandbox() -> Sandbox:
    if "relay" not in st.session_state:
        with st.spinner("Setting up your private copy of the helpdesk…"):
            st.session_state.relay = Sandbox()
    return st.session_state.relay


def reset() -> None:
    st.session_state.pop("relay", None)


def open_ticket(tid: str) -> None:
    sandbox().selected = tid
    st.switch_page("views/ticket.py")


__all__ = ["Email", "Command"]
