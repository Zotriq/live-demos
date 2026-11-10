"""Traced tool wrapper.

Every SpecForge tool is defined with Pydantic input/output models and wrapped by
:func:`traced_tool`, which:

  * fires the pre-hook (calling agent, tool name, state snapshot, status label, reasoning)
  * validates the raw input against the tool's input model
  * invokes the underlying callable
  * validates the return value against the tool's output model
  * logs the result
  * returns a LangChain-compatible ``StructuredTool``

There is intentionally no path to call a tool without this wrapper.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from specforge import context
from specforge.hooks.pre_hook import PreHookPayload, pre_hook
from specforge.tracing.logger import emit

TIn = TypeVar("TIn", bound=BaseModel)
TOut = TypeVar("TOut", bound=BaseModel)


def traced_tool(
    *,
    name: str,
    description: str,
    input_model: type[TIn],
    output_model: type[TOut],
    status_label: str,
) -> Callable[[Callable[[TIn], TOut]], StructuredTool]:
    """Decorator that turns a typed function into a traced ``StructuredTool``."""

    def decorator(fn: Callable[[TIn], TOut]) -> StructuredTool:
        def run(**kwargs) -> dict:
            ctx = context.current()
            pre_hook(PreHookPayload(agent=ctx.agent, tool_name=name, status_label=status_label,
                                    state_snapshot=ctx.state_snapshot, reasoning=ctx.reasoning))
            args = input_model.model_validate(kwargs)
            result = output_model.model_validate(fn(args))
            emit("tool_result", agent=ctx.agent, tool_name=name,
                 result={k: (v if not isinstance(v, str) or len(v) < 120 else f"<{len(v)} chars>")
                         for k, v in result.model_dump().items()})
            return result.model_dump()

        return StructuredTool.from_function(func=run, name=name, description=description, args_schema=input_model)

    return decorator
