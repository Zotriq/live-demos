"""Spec Writer.

  * receives state + plan from the Plan Agent
  * reads the plan via `read_plan_file` (served from the run cache when possible)
  * writes a spec-driven doc via `write_spec_file` to `.claude/spec/<feature-name>.md`
  * updates state: spec_path=<path>, status="done"
"""

from __future__ import annotations

from specforge import context
from specforge.hooks.post_hook import validate_output
from specforge.schemas import SPEC_SECTIONS, SpecDoc
from specforge.state import AgentState
from specforge.tools import read_plan_file, write_spec_file
from specforge.tracing.logger import emit

SYSTEM = ("You are the Spec Writer of SpecForge. Turn the implementation plan into a spec-driven document an AI "
          "coding assistant can implement from. Use exactly these sections: " + ", ".join(SPEC_SECTIONS) + ". "
          "Requirements and acceptance criteria are numbered and testable (Given/When/Then for criteria). "
          "Stay consistent with the plan and context; do not add scope. Output only the Markdown.")


def run_spec_writer(state: AgentState) -> AgentState:
    ctx = context.current()
    ctx.agent, ctx.state_snapshot = "spec_writer", state.model_dump()
    ctx.reasoning = "Read the plan and write a testable spec from it"
    plan = read_plan_file.invoke({"plan_path": state.plan_path})["contents"]
    user = f"Feature context:\n{state.model_dump_json(indent=2)}\n\nImplementation plan:\n{plan}"
    spec = validate_output("spec_writer", {"markdown": ctx.llm(SYSTEM, user)}, SpecDoc)
    spec_path = write_spec_file.invoke({"feature_name": state.feature_name, "markdown": spec.markdown})["spec_path"]
    emit("state", agent="spec_writer", status="done", spec_path=spec_path)
    return state.model_copy(update={"spec_path": spec_path, "status": "done"})
