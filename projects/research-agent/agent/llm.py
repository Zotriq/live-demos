"""Groq chat client, wrapped through LangChain's ``ChatGroq``.

LangChain is used *only* as the model client here — the ReAct orchestration in
``react_loop.py`` is hand-rolled.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from .config import MAIN_MODEL, require_groq_key

_ROLE_MAP = {
    "system": SystemMessage,
    "user": HumanMessage,
    "human": HumanMessage,
    "assistant": AIMessage,
    "ai": AIMessage,
}


def _to_lc(messages: list[dict[str, str]]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in messages:
        cls = _ROLE_MAP.get(m.get("role", "user"), HumanMessage)
        out.append(cls(content=m.get("content", "")))
    return out


class GroqLLM:
    """Minimal ``chat()`` surface over ``ChatGroq``."""

    def __init__(self, model: str = MAIN_MODEL, temperature: float = 0.0) -> None:
        self.model = model
        self.temperature = temperature
        self._api_key = require_groq_key()
        self._clients: dict[str, ChatGroq] = {}

    def _client(self, model: str) -> ChatGroq:
        if model not in self._clients:
            self._clients[model] = ChatGroq(
                model=model,
                temperature=self.temperature,
                api_key=self._api_key,
                max_retries=2,
            )
        return self._clients[model]

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        stop: list[str] | None = None,
        model: str | None = None,
    ) -> str:
        response = self._client(model or self.model).invoke(_to_lc(messages), stop=stop)
        content = response.content
        if isinstance(content, list):  # some providers return content parts
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return content.strip()
