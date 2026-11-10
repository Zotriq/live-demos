"""FastMCP server exposing SpecForge to Claude Code (stdio transport).

Run with::

    python -m specforge.server
"""

from __future__ import annotations

from fastmcp import FastMCP

from specforge.graph import run

mcp = FastMCP("specforge")


@mcp.tool()
def forge_spec(request: str, answers: dict[str, str] | None = None) -> dict:
    """Turn a one-line feature request into a plan and a spec-driven document.

    Runs Supervisor -> Plan Agent -> Spec Writer. If required context is missing the result
    has status "gathering" and `questions`; call again with the same request and `answers`
    (field -> answer). On success, `state` holds `plan_path` and `spec_path`.
    """
    result = run(request, answers=answers)
    result["trace"] = [{k: v for k, v in e.items() if k != "state_snapshot"} for e in result["trace"]]
    return result


def main() -> None:
    mcp.run()  # stdio transport by default


if __name__ == "__main__":
    main()
