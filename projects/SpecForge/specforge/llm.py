"""Default LLM: any OpenAI-compatible chat endpoint (Groq by default)."""

from __future__ import annotations

import json
import os
import re

from specforge.config import settings


def default_llm():
    from openai import OpenAI

    key = settings.api_key or os.getenv("SPECFORGE_API_KEY") or os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Set SPECFORGE_API_KEY or GROQ_API_KEY")
    client = OpenAI(api_key=key, base_url=settings.base_url)

    def call(system: str, user: str) -> str:
        r = client.chat.completions.create(
            model=settings.model, temperature=settings.temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return r.choices[0].message.content or ""

    return call


def parse_json(text: str) -> object:
    """Parse a JSON object from a model reply, tolerating code fences."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1] if start >= 0 else text)
