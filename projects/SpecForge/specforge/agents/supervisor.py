"""Supervisor agent.

  * reads the project overview (CLAUDE.md) once, via the cached file reader
  * gathers feature context: feature_name, description, target_layer, data_source,
    user_facing, tech_stack
  * asks the user for any missing required field: never assumes a default
  * once nothing is missing, sets status="planning" and hands off to the Plan Agent
"""

from __future__ import annotations

import json

from specforge import context
from specforge.config import settings
from specforge.hooks.post_hook import validate_output
from specforge.llm import parse_json
from specforge.plugins import file_io
from specforge.schemas import SupervisorOutput
from specforge.state import REQUIRED_CONTEXT_FIELDS, AgentState, PartialContext
from specforge.tracing.logger import emit

SYSTEM = """You are the Supervisor of SpecForge. Extract feature context from a feature request.
Fill a field ONLY if the request, the user's answers, or the project overview states it clearly. Never guess
or assume a default: leave it null. For every null field, write one short, specific question for the user.

Fields:
- feature_name: short kebab-free name, e.g. "wishlist"
- description: one or two sentences
- target_layer: one of "storefront", "backend", "admin", "file"
- data_source: where the data lives (e.g. "postgres.wishlists", "Stripe API")
- user_facing: true or false
- tech_stack: frameworks/languages used

Reply with JSON only: {"feature_name": ..., "description": ..., "target_layer": ..., "data_source": ...,
"user_facing": ..., "tech_stack": ..., "questions": {"<field>": "<question>", ...}}"""


def _overview(ctx) -> str:
    try:
        return file_io.read_text(settings.project_overview, cache=ctx.cache, allow_overview=True)[:6000]
    except (FileNotFoundError, file_io.ScopeViolation):
        return "(no project overview found)"


def run_supervisor(partial: PartialContext, answers: dict[str, str] | None = None) -> tuple[PartialContext, dict[str, str]]:
    """Returns the (possibly still incomplete) context and questions for missing fields."""
    ctx = context.current()
    ctx.agent, ctx.reasoning = "supervisor", "Gathering required feature context before planning"
    ctx.state_snapshot = partial.model_dump()
    emit("state", agent="supervisor", status="gathering")
    user = (f"Project overview:\n{_overview(ctx)}\n\nFeature request: {partial.raw_request}\n\n"
            f"Answers from the user so far: {json.dumps(answers or {})}\n\n"
            f"Already known: {json.dumps({k: v for k, v in partial.model_dump().items() if v not in (None, '')})}")
    out = validate_output("supervisor", parse_json(ctx.llm(SYSTEM, user)), SupervisorOutput)
    merged = partial.model_copy(update={k: v for k, v in out.model_dump(exclude={"questions"}).items()
                                        if v not in (None, "") and k != "raw_request"})
    missing = [f for f in REQUIRED_CONTEXT_FIELDS if getattr(merged, f) in (None, "")]
    questions = {f: out.questions.get(f) or f"Please provide the {f.replace('_', ' ')}." for f in missing}
    if questions:
        emit("needs_input", agent="supervisor", missing=missing)
    return merged, questions


def to_agent_state(partial: PartialContext) -> AgentState:
    data = partial.model_dump(exclude={"raw_request"})
    state = validate_output("supervisor", data, AgentState)
    state.status = "planning"
    emit("handoff", **{"from": "supervisor", "to": "plan_agent"}, feature=state.feature_name)
    return state
