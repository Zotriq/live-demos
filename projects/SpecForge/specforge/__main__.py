"""CLI: ``python -m specforge "I wanna build a wishlist"``.

Asks for any missing context on the terminal, then writes the plan and the spec.
The MCP server (``python -m specforge.server``) is the main interface for Claude Code.
"""

from __future__ import annotations

import sys

from specforge.graph import run


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print('usage: python -m specforge "<one-line feature request>"')
        return 2
    request, answers = " ".join(argv), {}
    while True:
        result = run(request, answers=answers)
        if result["status"] != "gathering":
            break
        for field, question in result["questions"].items():
            answers[field] = input(f"{question} ")
    if result["status"] == "error":
        print(result["error"])
        return 1
    print(f"Plan: {result['state']['plan_path']}\nSpec: {result['state']['spec_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
