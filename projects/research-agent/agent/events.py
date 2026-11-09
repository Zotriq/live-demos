"""Structured events emitted during an agent run (shared by console, file, and SSE sinks)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "run_start",
    "thought",
    "action",
    "tool_input",
    "observation",
    "tool_latency",
    "summary_updated",
    "final_answer",
    "error",
    "run_end",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentEvent(BaseModel):
    type: EventType
    timestamp: str = Field(default_factory=_now_iso)
    iteration: int = 0
    session_id: str = "cli"
    payload: dict[str, Any] = Field(default_factory=dict)

    def sse(self) -> str:
        """Serialize as a single Server-Sent-Events frame."""
        return f"data: {self.model_dump_json()}\n\n"
