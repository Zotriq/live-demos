"""The conversation loop: history + new message -> LLM with tools -> run tools -> final reply."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from .store import Store
from .tools import BUSINESS, TOOL_SCHEMAS, Salon, make_tools

log = logging.getLogger("wa_agent")
MAX_TOOL_ROUNDS = 5

SYSTEM = """You are the WhatsApp assistant for {name}, a salon in Lahore. Today is {today}.

- Reply in the customer's language (English, Urdu or Roman Urdu). Keep messages short and friendly: this is WhatsApp.
- Use the tools for prices, hours, availability and bookings. Never invent times or prices.
- Before booking, confirm the service, date, time and the customer's name.
- After booking, share the booking code.
- Use handoff_to_human for complaints, refunds, special requests, or if the customer asks for a person."""


class ChatModel(Protocol):
    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        """Return an assistant message dict: {"role": "assistant", "content": str|None, "tool_calls": [...]}"""


class OpenAIChatModel:
    def __init__(self, api_key: str | None, model: str = "gpt-4o-mini", base_url: str | None = None):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        msg = self.client.chat.completions.create(model=self.model, temperature=0.3, messages=messages, tools=tools).choices[0].message
        out: dict[str, Any] = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            out["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in msg.tool_calls
            ]
        return out


def reply(store: Store, model: ChatModel, salon: Salon, phone: str, text: str, on_handoff) -> str:
    store.add(phone, {"role": "user", "content": text})
    tools = make_tools(salon, phone, on_handoff)
    system = {"role": "system", "content": SYSTEM.format(name=BUSINESS["name"], today=salon.now().strftime("%A %d %B %Y"))}

    for _ in range(MAX_TOOL_ROUNDS):
        message = model.complete([system, *store.history(phone)], TOOL_SCHEMAS)
        store.add(phone, message)
        calls = message.get("tool_calls") or []
        if not calls:
            return (message.get("content") or "").strip() or "Sorry, could you say that again?"
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
                result = tools[name](**args)
            except (KeyError, TypeError, ValueError) as exc:
                result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            store.add(phone, {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, default=str)})

    log.warning("tool loop limit reached for %s", phone)
    return "Sorry, I'm having trouble with that. A team member will help you shortly."

