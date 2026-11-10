"""The single shared state object threaded through the LangGraph graph.

Every node reads and writes ``AgentState`` directly; nothing is passed
out-of-band between agents.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TargetLayer = Literal["storefront", "backend", "admin", "file"]
Status = Literal["gathering", "planning", "spec_writing", "done", "error"]

# Fields the Supervisor must have populated before handoff to the Plan Agent.
REQUIRED_CONTEXT_FIELDS: tuple[str, ...] = (
    "feature_name",
    "description",
    "target_layer",
    "data_source",
    "user_facing",
    "tech_stack",
)


class AgentState(BaseModel):
    """Shared state for the Supervisor -> Plan Agent -> Spec Writer sequence."""

    feature_name: str
    description: str
    target_layer: TargetLayer
    data_source: str
    user_facing: bool
    tech_stack: str
    plan_path: str | None = None
    spec_path: str | None = None
    status: Status = "gathering"

    def missing_required_fields(self) -> list[str]:
        """Return required context fields that are unset or blank."""
        missing: list[str] = []
        for name in REQUIRED_CONTEXT_FIELDS:
            value = getattr(self, name, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(name)
        return missing


class PartialContext(BaseModel):
    """Context under construction while the Supervisor interviews the user.

    All fields optional; promoted to :class:`AgentState` once complete.
    """

    feature_name: str | None = None
    description: str | None = None
    target_layer: TargetLayer | None = None
    data_source: str | None = None
    user_facing: bool | None = None
    tech_stack: str | None = None
    raw_request: str = Field(default="", description="The original one-line feature request.")
