"""Hybrid conversation memory: verbatim sliding window + background rolling summary.

In-memory only — nothing is persisted across process restarts.
"""

from __future__ import annotations

import threading

from .config import SUMMARY_MODEL, WINDOW_TURNS
from .llm import GroqLLM
from .logging_hooks import ExecutionLogger

_SUMMARY_SYSTEM = (
    "You maintain a running summary of a conversation between a user and a research "
    "assistant. Merge the new exchanges into the existing summary. Keep it under 200 "
    "words, factual, third person, and preserve concrete facts, names, and numbers. "
    "Return only the updated summary text."
)


class HybridMemory:
    def __init__(
        self,
        llm: GroqLLM | None = None,
        *,
        window: int = WINDOW_TURNS,
        logger: ExecutionLogger | None = None,
        summary_model: str = SUMMARY_MODEL,
    ) -> None:
        self.llm = llm or GroqLLM()
        self.window = window
        self.logger = logger
        self.summary_model = summary_model
        self.turns: list[tuple[str, str]] = []
        self.summary: str = ""
        self._lock = threading.Lock()
        self._fold_thread: threading.Thread | None = None

    # ------------------------------------------------------------------ #
    def add_turn(self, user: str, assistant: str, *, session_id: str = "cli") -> None:
        with self._lock:
            self.turns.append((user, assistant))
            overflow: list[tuple[str, str]] = []
            while len(self.turns) > self.window:
                overflow.append(self.turns.pop(0))
        if overflow:
            self._fold_thread = threading.Thread(
                target=self._fold, args=(overflow, session_id), daemon=True
            )
            self._fold_thread.start()

    def render(self) -> str:
        with self._lock:
            summary, turns = self.summary, list(self.turns)
        parts: list[str] = []
        if summary:
            parts.append(f"Summary of earlier conversation:\n{summary}")
        if turns:
            recent = "\n".join(f"User: {u}\nAssistant: {a}" for u, a in turns)
            parts.append(f"Recent turns:\n{recent}")
        return "\n\n".join(parts)

    def wait_for_fold(self, timeout: float | None = None) -> None:
        """Test/CLI helper — block until the background summariser finishes."""
        thread = self._fold_thread
        if thread is not None:
            thread.join(timeout)

    # ------------------------------------------------------------------ #
    def _fold(self, overflow: list[tuple[str, str]], session_id: str) -> None:
        convo = "\n".join(f"User: {u}\nAssistant: {a}" for u, a in overflow)
        with self._lock:
            existing = self.summary or "(none)"
        messages = [
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {
                "role": "user",
                "content": f"Existing summary:\n{existing}\n\nNew exchanges:\n{convo}",
            },
        ]
        try:
            new_summary = self.llm.chat(messages, model=self.summary_model).strip()
        except Exception:  # noqa: BLE001 - summariser failure must not break the agent
            return
        with self._lock:
            self.summary = new_summary
            size = len(new_summary)
        if self.logger is not None:
            self.logger.event("summary_updated", session_id=session_id, chars=size)
