"""Execute n8n Code node JavaScript with Node.js, exactly as the workflow runs it."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path

RUNNER = Path(__file__).with_name("n8n_runner.mjs")


class NodeError(RuntimeError):
    pass


def available() -> bool:
    return shutil.which("node") is not None


def run_code(code: str, *, input: list[dict] | None = None, nodes: dict[str, list[dict]] | None = None,
             today: str | None = None) -> list[dict]:
    payload = {"code": code, "input": input or [], "nodes": nodes or {}, "today": today or dt.date.today().isoformat()}
    result = subprocess.run(["node", str(RUNNER)], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise NodeError(result.stderr.strip() or "Code node failed")
    return json.loads(result.stdout)
