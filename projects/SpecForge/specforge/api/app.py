"""FastAPI debug/dashboard app (optional).

Endpoints (planned):
  * GET  /health        — liveness
  * GET  /runs          — list recent pipeline runs
  * GET  /runs/{id}     — full trace for one run
  * GET  /runs/{id}/state — final AgentState
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="SpecForge Debug", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
