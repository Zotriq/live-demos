"""Tool registry."""

from __future__ import annotations

from .base import Tool
from .file_read import FileReadTool
from .web_search import WebSearchTool


def build_registry() -> dict[str, Tool]:
    tools: list[Tool] = [WebSearchTool(), FileReadTool()]
    return {t.name: t for t in tools}


TOOL_REGISTRY: dict[str, Tool] = build_registry()

__all__ = ["Tool", "TOOL_REGISTRY", "build_registry", "WebSearchTool", "FileReadTool"]
