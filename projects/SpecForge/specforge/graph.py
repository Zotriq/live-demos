"""LangGraph orchestration graph.

Fixed sequential order (v1, no concurrency):

    supervisor --(context complete)--> plan_agent -> spec_writer -> END
        └──────(fields missing)──────> END  (questions returned to the user)

The Supervisor never guesses: when required context is missing the run stops with
status "gathering" and the questions; call :func:`run` again with ``answers``.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from specforge import context
from specforge.agents.plan_agent import run_plan_agent
from specforge.agents.spec_writer import run_spec_writer
from specforge.agents.supervisor import run_supervisor, to_agent_state
from specforge.hooks.post_hook import PipelineHalt
from specforge.state import AgentState, PartialContext
from specforge.tracing.logger import capture, emit


class PipelineState(TypedDict, total=False):
    partial: PartialContext
    answers: dict[str, str]
    questions: dict[str, str]
    state: AgentState


def _supervisor(s: PipelineState) -> PipelineState:
    partial, questions = run_supervisor(s["partial"], s.get("answers"))
    out: PipelineState = {"partial": partial, "questions": questions}
    if not questions:
        out["state"] = to_agent_state(partial)
    return out


def _plan(s: PipelineState) -> PipelineState:
    return {"state": run_plan_agent(s["state"])}


def _spec(s: PipelineState) -> PipelineState:
    return {"state": run_spec_writer(s["state"])}


def build_graph():
    """Construct and compile the SpecForge LangGraph graph."""
    g = StateGraph(PipelineState)
    g.add_node("supervisor", _supervisor)
    g.add_node("plan_agent", _plan)
    g.add_node("spec_writer", _spec)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", lambda s: END if s.get("questions") else "plan_agent")
    g.add_edge("plan_agent", "spec_writer")
    g.add_edge("spec_writer", END)
    return g.compile()


def run(raw_request: str, answers: dict[str, str] | None = None, llm: context.LLM | None = None) -> dict[str, Any]:
    """Run the pipeline for one request. Returns status, questions (if any), final state and trace."""
    if llm is None:
        from specforge.llm import default_llm
        llm = default_llm()
    token = context.activate(context.RunContext(llm=llm))
    try:
        with capture() as trace:
            emit("run_start", request=raw_request)
            try:
                final = build_graph().invoke({"partial": PartialContext(raw_request=raw_request), "answers": answers or {}})
            except PipelineHalt as halt:
                emit("run_end", status="error")
                return {"status": "error", "error": str(halt), "questions": {}, "state": None, "trace": trace}
            state = final.get("state")
            status = state.status if state else "gathering"
            emit("run_end", status=status)
            return {"status": status, "questions": final.get("questions", {}),
                    "context": final["partial"].model_dump(), "state": state.model_dump() if state else None,
                    "trace": trace}
    finally:
        context.deactivate(token)
