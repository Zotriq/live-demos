"""ReAct system-prompt construction."""

from __future__ import annotations

from .tools import Tool

_FORMAT_BLOCK = """\
Use this exact format, one field per line:

Question: the input question you must answer
Thought: your reasoning about what to do next
Action: the tool to use, exactly one of [{tool_names}]
Action Input: the input to the tool
Observation: the result of the tool (filled in for you)
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now know the final answer
Final Answer: the complete answer to the original question

Rules:
- Every reply MUST begin with "Thought:".
- Emit exactly one Action per Thought, then STOP and wait for the Observation.
- Break multi-hop questions into separate searches; do not guess facts you can look up.
- When you have enough information, reply with "Thought:" then "Final Answer:" and nothing after it.

Example:
Question: Who is the current CEO of the company that owns Instagram?
Thought: Instagram is owned by Meta Platforms. I should confirm Meta's current CEO.
Action: web_search
Action Input: current CEO of Meta Platforms
Observation: Mark Zuckerberg is the chairman and CEO of Meta Platforms.
Thought: I now know the final answer.
Final Answer: Mark Zuckerberg."""


def _tool_catalog(tools: dict[str, Tool]) -> str:
    return "\n".join(f"- {t.name}: {t.description}" for t in tools.values())


def build_system_prompt(tools: dict[str, Tool], memory_block: str) -> str:
    tool_names = ", ".join(tools)
    parts = [
        "You are an autonomous research agent that answers questions by reasoning "
        "step by step and using tools.",
        "",
        "Available tools:",
        _tool_catalog(tools),
        "",
        _FORMAT_BLOCK.format(tool_names=tool_names),
    ]
    if memory_block.strip():
        parts += ["", "Conversation context:", memory_block.strip()]
    return "\n".join(parts)
