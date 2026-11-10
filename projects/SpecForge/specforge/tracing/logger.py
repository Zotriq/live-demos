"""Structured, real-time trace logger.

Emits one line per event as it happens: tool calls, state transitions, agent handoffs,
reasoning. Optionally mirrors events as JSONL to ``settings.trace_file``, and hands them
to any subscribers (the MCP tool and the demo UI collect a run's trace this way).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from specforge.config import settings

_subscribers: list[Callable[[dict], None]] = []

try:  # Rich is optional at runtime
    from rich.console import Console

    _console: Console | None = Console(stderr=True)
except Exception:  # pragma: no cover
    _console = None

_STYLE = {"tool_call": "cyan", "tool_result": "green", "handoff": "magenta", "state": "yellow", "error": "bold red"}


def emit(event: str, **fields: Any) -> None:
    """Emit a single trace event. Never raises: tracing must not break a run."""
    record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    try:
        if settings.trace_to_stdout:
            line = " ".join(f"{k}={v}" for k, v in fields.items() if k != "state_snapshot")
            if _console:
                _console.print(f"[{_STYLE.get(event, 'white')}]{event}[/] {line}", highlight=False)
            else:
                print(event, line)
        if settings.trace_file:
            with open(settings.trace_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        for sub in list(_subscribers):
            sub(record)
    except Exception:  # pragma: no cover
        pass


@contextmanager
def capture() -> Iterator[list[dict]]:
    """Collect every event emitted inside the block."""
    events: list[dict] = []
    _subscribers.append(events.append)
    try:
        yield events
    finally:
        _subscribers.remove(events.append)
