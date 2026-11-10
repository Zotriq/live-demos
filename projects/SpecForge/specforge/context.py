"""Per-run context: the LLM, the read cache, the current agent and state snapshot.

Held in a ContextVar so tools (which LangChain calls with only their arguments) can
still report who called them and what the state was, for the pre-hook trace.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field

from specforge.plugins.file_io import RunCache

LLM = Callable[[str, str], str]  # (system, user) -> text


@dataclass
class RunContext:
    llm: LLM
    cache: RunCache = field(default_factory=RunCache)
    agent: str = "pipeline"
    state_snapshot: dict = field(default_factory=dict)
    reasoning: str | None = None


_current: ContextVar[RunContext | None] = ContextVar("specforge_run", default=None)


def current() -> RunContext:
    ctx = _current.get()
    if ctx is None:
        raise RuntimeError("No active SpecForge run (use specforge.graph.run)")
    return ctx


def activate(ctx: RunContext):
    return _current.set(ctx)


def deactivate(token) -> None:
    _current.reset(token)
