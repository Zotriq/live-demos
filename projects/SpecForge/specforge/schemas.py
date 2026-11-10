"""Schemas the post-hook validates each agent's output against."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from specforge.state import PartialContext

PLAN_SECTIONS = ("## Goal", "## Approach", "## Steps", "## Risks")
SPEC_SECTIONS = ("## Overview", "## Requirements", "## Data model", "## Interfaces", "## Acceptance criteria", "## Out of scope")


def _require(markdown: str, sections: tuple[str, ...]) -> str:
    missing = [s for s in sections if s.lower() not in markdown.lower()]
    if missing:
        raise ValueError(f"missing sections: {', '.join(missing)}")
    if len(markdown.strip()) < 200:
        raise ValueError("document is too short to be useful")
    return markdown


class SupervisorOutput(PartialContext):
    """What the Supervisor extracted; unknown fields stay null (never guessed)."""

    questions: dict[str, str] = {}


class PlanDoc(BaseModel):
    markdown: str

    @field_validator("markdown")
    @classmethod
    def _sections(cls, v: str) -> str:
        return _require(v, PLAN_SECTIONS)


class SpecDoc(BaseModel):
    markdown: str

    @field_validator("markdown")
    @classmethod
    def _sections(cls, v: str) -> str:
        return _require(v, SPEC_SECTIONS)
