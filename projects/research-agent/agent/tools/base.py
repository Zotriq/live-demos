"""Tool contract shared by every plugin."""

from __future__ import annotations

import abc
import json
from typing import Any

from pydantic import BaseModel, ValidationError


class Tool(abc.ABC):
    """A callable the agent can invoke from an ``Action`` step."""

    name: str
    description: str
    args_schema: type[BaseModel]

    def coerce_input(self, raw: Any) -> BaseModel:
        """Turn a parsed ``Action Input`` (str or dict) into the typed schema."""
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped.startswith("{"):
                try:
                    raw = json.loads(stripped)
                except json.JSONDecodeError:
                    raw = {self._primary_field(): stripped}
            else:
                raw = {self._primary_field(): stripped}
        return self.args_schema(**raw)

    def _primary_field(self) -> str:
        return next(iter(self.args_schema.model_fields))

    def __call__(self, raw: Any) -> str:
        try:
            args = self.coerce_input(raw)
        except ValidationError as exc:
            return f"Invalid input for tool '{self.name}': {exc}"
        return self.run(args)

    @abc.abstractmethod
    def run(self, args: BaseModel) -> str:  # pragma: no cover - interface
        ...
