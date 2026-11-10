"""Plan Agent.

  * receives complete state from the Supervisor
  * calls `check_existing_plan`: reuses an existing plan if present (cost/latency)
  * proposes an implementation plan grounded in the feature context
  * writes it via `write_plan_file` to `.claude/plans/<feature-name>.md`
  * updates state: plan_path=<path>, status="spec_writing"
"""

from __future__ import annotations

from specforge import context
from specforge.hooks.post_hook import validate_output
from specforge.schemas import PLAN_SECTIONS, PlanDoc
from specforge.state import AgentState
from specforge.tools import check_existing_plan, write_plan_file
from specforge.tracing.logger import emit

SYSTEM = ("You are the Plan Agent of SpecForge. Write a concise, concrete implementation plan in Markdown for "
          "the feature below. Use exactly these sections: " + ", ".join(PLAN_SECTIONS) + ". Steps must be a "
          "numbered list of small, verifiable tasks naming files/modules to touch. Ground every step in the given "
          "context; do not invent requirements. Output only the Markdown.")


def run_plan_agent(state: AgentState) -> AgentState:
    ctx = context.current()
    ctx.agent, ctx.state_snapshot = "plan_agent", state.model_dump()
    ctx.reasoning = "Reuse an existing plan if there is one, otherwise draft and save a new plan"
    existing = check_existing_plan.invoke({"feature_name": state.feature_name})
    if existing["exists"]:
        emit("state", agent="plan_agent", note="reusing existing plan")
        plan_path = existing["plan_path"]
    else:
        markdown = ctx.llm(SYSTEM, state.model_dump_json(indent=2, exclude={"plan_path", "spec_path", "status"}))
        plan = validate_output("plan_agent", {"markdown": markdown}, PlanDoc)
        plan_path = write_plan_file.invoke({"feature_name": state.feature_name, "markdown": plan.markdown})["plan_path"]
    new = state.model_copy(update={"plan_path": plan_path, "status": "spec_writing"})
    emit("handoff", **{"from": "plan_agent", "to": "spec_writer"}, plan_path=plan_path)
    return new
