"""Post-hook: runs after every agent's output.

Validates the raw agent output against its expected Pydantic schema before it is
accepted into state. On failure, raises :class:`PipelineHalt` so the graph stops and
surfaces the validation error instead of passing bad data downstream.
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from specforge.tracing.logger import emit


class PipelineHalt(RuntimeError):
    """Raised when an agent's output fails schema validation."""

    def __init__(self, agent: str, error: ValidationError) -> None:
        super().__init__(f"{agent} output failed validation:\n{error}")
        self.agent = agent
        self.error = error


def validate_output(agent: str, raw: object, schema: type[BaseModel]) -> BaseModel:
    try:
        model = schema.model_validate(raw)
    except ValidationError as exc:
        emit("error", agent=agent, schema=schema.__name__, errors=exc.errors(include_url=False))
        raise PipelineHalt(agent, exc) from exc
    emit("validated", agent=agent, schema=schema.__name__)
    return model
