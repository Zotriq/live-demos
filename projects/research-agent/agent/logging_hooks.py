"""Dual-sink execution logger: colour console + rolling file + live SSE subscribers."""

from __future__ import annotations

import asyncio
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from colorama import Fore, Style
from colorama import init as _colorama_init

from .config import EXECUTION_LOG_PATH
from .events import AgentEvent, EventType

_colorama_init()

_COLOR: dict[str, str] = {
    "run_start": Fore.WHITE + Style.BRIGHT,
    "thought": Fore.CYAN,
    "action": Fore.YELLOW + Style.BRIGHT,
    "tool_input": Fore.YELLOW,
    "observation": Fore.GREEN,
    "tool_latency": Fore.MAGENTA,
    "summary_updated": Fore.BLUE,
    "final_answer": Fore.WHITE + Style.BRIGHT,
    "error": Fore.RED + Style.BRIGHT,
    "run_end": Fore.WHITE + Style.DIM,
}


def _render(event: AgentEvent) -> str:
    """One-line human-readable rendering of an event's payload."""
    p = event.payload
    t = event.type
    if t == "run_start":
        return f"QUESTION: {p.get('question', '')}"
    if t == "thought":
        return f"Thought: {p.get('text', '')}"
    if t == "action":
        return f"Action: {p.get('tool', '')}"
    if t == "tool_input":
        return f"Action Input: {p.get('input', '')}"
    if t == "observation":
        return f"Observation: {p.get('text', '')}"
    if t == "tool_latency":
        return f"[{p.get('tool', '')}] took {p.get('ms', 0)} ms"
    if t == "summary_updated":
        return f"Memory summary updated ({p.get('chars', 0)} chars)"
    if t == "final_answer":
        return f"Final Answer: {p.get('text', '')}"
    if t == "error":
        return f"ERROR: {p.get('message', '')}"
    if t == "run_end":
        return f"Run finished in {p.get('iterations', 0)} iteration(s)"
    return str(p)


class ExecutionLogger:
    """Fan-out sink. Thread-safe; agent loop runs in a worker thread while
    asyncio subscribers live on the main event loop."""

    def __init__(
        self,
        *,
        to_console: bool = True,
        to_file: bool = True,
        file_path: Path = EXECUTION_LOG_PATH,
    ) -> None:
        self.to_console = to_console
        self.to_file = to_file
        self.file_path = Path(file_path)
        self._lock = threading.Lock()
        self._subscribers: list[tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = []

    # -- subscriber management (used by the SSE endpoint) -------------------- #
    def subscribe(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._subscribers.append((queue, loop))

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s[0] is not queue]

    # -- emit -------------------------------------------------------------- #
    def emit(self, event: AgentEvent) -> None:
        if self.to_console:
            self._write_console(event)
        if self.to_file:
            self._write_file(event)
        with self._lock:
            subs = list(self._subscribers)
        for queue, loop in subs:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except RuntimeError:
                pass  # loop already closed

    def event(
        self,
        type: EventType,
        *,
        iteration: int = 0,
        session_id: str = "cli",
        **payload: object,
    ) -> AgentEvent:
        evt = AgentEvent(
            type=type, iteration=iteration, session_id=session_id, payload=dict(payload)
        )
        self.emit(evt)
        return evt

    # -- tool timing ----------------------------------------------------- #
    @contextmanager
    def timed_tool(
        self, tool: str, *, iteration: int = 0, session_id: str = "cli"
    ) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            ms = round((time.perf_counter() - start) * 1000, 1)
            self.event(
                "tool_latency", iteration=iteration, session_id=session_id, tool=tool, ms=ms
            )

    # -- private sinks ------------------------------------------------------- #
    @staticmethod
    def _stamp(event: AgentEvent) -> str:
        try:
            dt = datetime.fromisoformat(event.timestamp)
        except ValueError:
            dt = datetime.now()
        return dt.strftime("%H:%M:%S.") + f"{dt.microsecond // 1000:03d}"

    def _write_console(self, event: AgentEvent) -> None:
        colour = _COLOR.get(event.type, "")
        line = f"{Style.DIM}{self._stamp(event)}{Style.RESET_ALL} {colour}{_render(event)}{Style.RESET_ALL}"
        print(line, flush=True)

    def _write_file(self, event: AgentEvent) -> None:
        try:
            with self.file_path.open("a", encoding="utf-8") as fh:
                fh.write(f"{self._stamp(event)} [{event.type}] {_render(event)}\n")
        except OSError:
            pass
