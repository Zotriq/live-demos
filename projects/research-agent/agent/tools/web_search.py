"""Web search tool backed by SerpAPI (Google engine)."""

from __future__ import annotations

import requests
from pydantic import BaseModel, Field

from ..config import SEARCH_RESULTS, require_serpapi_key
from .base import Tool

_ENDPOINT = "https://serpapi.com/search"
_TIMEOUT = 35
_RETRIES = 1


class WebSearchArgs(BaseModel):
    query: str = Field(..., description="Natural-language search query")


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the live web for facts, news, people, and definitions. "
        "Input: a single search query string. Returns the top results as text."
    )
    args_schema = WebSearchArgs

    def run(self, args: WebSearchArgs) -> str:  # type: ignore[override]
        try:
            key = require_serpapi_key()
        except RuntimeError as exc:
            return f"web_search unavailable: {exc}"

        params = {
            "q": args.query,
            "api_key": key,
            "engine": "google",
            "num": SEARCH_RESULTS,
        }
        last_exc: Exception | None = None
        for attempt in range(_RETRIES + 1):
            try:
                resp = requests.get(_ENDPOINT, params=params, timeout=_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as exc:
                last_exc = exc
            except ValueError:
                return "web_search error: could not decode SerpAPI response"
        else:
            return f"web_search error: {last_exc}"

        if err := data.get("error"):
            return f"web_search error: {err}"

        return self._format(data)

    @staticmethod
    def _format(data: dict) -> str:
        lines: list[str] = []

        box = data.get("answer_box") or {}
        direct = box.get("answer") or box.get("snippet") or box.get("result")
        if direct:
            lines.append(f"Answer box: {direct}")

        kg = data.get("knowledge_graph") or {}
        if kg.get("description"):
            title = kg.get("title", "")
            lines.append(f"Knowledge graph ({title}): {kg['description']}")

        for i, item in enumerate(data.get("organic_results", [])[:SEARCH_RESULTS], 1):
            title = item.get("title", "").strip()
            snippet = item.get("snippet", "").strip()
            link = item.get("link", "").strip()
            lines.append(f"{i}. {title} — {snippet} ({link})")

        return "\n".join(lines) if lines else "No results found."
