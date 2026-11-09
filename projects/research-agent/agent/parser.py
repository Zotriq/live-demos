"""Parse a single ReAct step out of the model's raw text output."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

_ACTION_RE = re.compile(r"Action\s*:\s*(.+?)\s*(?:\n|$)", re.IGNORECASE)
_INPUT_RE = re.compile(
    r"Action\s*Input\s*:\s*(.*?)(?:\nObservation\s*:|\nThought\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_FINAL_RE = re.compile(r"Final\s*Answer\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)
_THOUGHT_RE = re.compile(
    r"Thought\s*:\s*(.*?)(?:\nAction\s*:|\nFinal\s*Answer\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)


class ParsedStep(BaseModel):
    thought: str = ""
    action: str | None = None
    action_input: Any = None
    final_answer: str | None = None
    error: str | None = None  # set when the text could not be parsed into a valid step

    @property
    def is_final(self) -> bool:
        return self.final_answer is not None


def _clean_input(raw: str) -> Any:
    raw = raw.strip().strip("`").strip()
    if raw.startswith("{") or raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    # strip a single pair of wrapping quotes
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        raw = raw[1:-1]
    return raw


def parse_step(text: str) -> ParsedStep:
    thought_match = _THOUGHT_RE.search(text)
    thought = thought_match.group(1).strip() if thought_match else ""

    final_match = _FINAL_RE.search(text)
    if final_match:
        return ParsedStep(thought=thought, final_answer=final_match.group(1).strip())

    action_match = _ACTION_RE.search(text)
    input_match = _INPUT_RE.search(text)
    if action_match:
        action = action_match.group(1).strip().strip("`").strip()
        raw_input = input_match.group(1) if input_match else ""
        return ParsedStep(
            thought=thought,
            action=action,
            action_input=_clean_input(raw_input),
        )

    return ParsedStep(
        thought=thought,
        error=(
            "Could not parse an Action or Final Answer. Respond using the required "
            "format: a 'Thought:' line, then either 'Action:' + 'Action Input:' or "
            "'Final Answer:'."
        ),
    )


def freetext_final(text: str) -> str:
    """Best-effort answer extraction from an unparseable response.

    Used as a fallback when the model has clearly finished reasoning but forgot
    the ``Final Answer:`` label.
    """
    final_match = _FINAL_RE.search(text)
    if final_match:
        return final_match.group(1).strip()
    stripped = re.sub(r"^\s*Thought\s*:\s*", "", text.strip(), flags=re.IGNORECASE)
    return stripped.strip()
