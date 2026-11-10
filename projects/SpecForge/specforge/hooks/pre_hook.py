"""Pre-hook: runs before every tool call.

Logs, via the real-time tracer: calling agent, tool name, a snapshot of current
AgentState, a status label, and the agent's reasoning for the step (never discarded).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from specforge.tracing.logger import emit

StatusLabel = Literal["reading_file", "understanding", "generating_plan", "writing_spec", "output"]


class PreHookPayload(BaseModel):
    agent: str
    tool_name: str
    status_label: StatusLabel
    state_snapshot: dict
    reasoning: str | None = None


def pre_hook(payload: PreHookPayload) -> None:
    emit("tool_call", **payload.model_dump())
