"""LLM extraction: invoice text -> validated `Invoice` object.

Two providers are included. Both ask the model for JSON that matches the
Pydantic schema, and both go through the same validation, so swapping
providers never changes the output format.
"""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import ValidationError

from .schema import Invoice

INSTRUCTIONS = """Extract the invoice below into JSON.

Rules:
- Copy values exactly as printed; do not calculate or "fix" totals.
- Numbers: plain decimals without currency symbols or thousands separators (1249.50).
- Dates: YYYY-MM-DD.
- currency: ISO code (USD, EUR, GBP, PKR...). Infer from symbols if needed ($ -> USD, € -> EUR, £ -> GBP, Rs -> PKR).
- Use null for fields that are not on the invoice.
"""


class ExtractionError(RuntimeError):
    pass


class Extractor(Protocol):
    def extract(self, text: str) -> Invoice: ...


def parse_invoice_json(raw: str | dict) -> Invoice:
    data = json.loads(raw) if isinstance(raw, str) else raw
    try:
        return Invoice.model_validate(data)
    except ValidationError as exc:
        raise ExtractionError(f"Model output did not match the invoice schema: {exc.errors()[0]['msg']}") from exc


class OpenAIExtractor:
    """Uses OpenAI structured outputs (any OpenAI-compatible endpoint that supports json_schema)."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini", base_url: str | None = None):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def extract(self, text: str) -> Invoice:
        schema = Invoice.model_json_schema()
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_schema", "json_schema": {"name": "invoice", "schema": schema}},
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": text},
            ],
        )
        return parse_invoice_json(response.choices[0].message.content or "{}")


class AnthropicExtractor:
    """Uses Claude tool use with the invoice schema as the tool's input schema."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-5-5"):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def extract(self, text: str) -> Invoice:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=INSTRUCTIONS,
            tools=[{"name": "save_invoice", "description": "Save the extracted invoice", "input_schema": Invoice.model_json_schema()}],
            tool_choice={"type": "tool", "name": "save_invoice"},
            messages=[{"role": "user", "content": text}],
        )
        for block in response.content:
            if block.type == "tool_use":
                return parse_invoice_json(block.input)
        raise ExtractionError("Model did not return the invoice tool call")
