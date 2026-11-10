# SpecForge

## Project overview

SpecForge is a sequential multi-agent CLI tool that turns a one-line feature
request ("I wanna build X") into a structured, spec-driven document. It runs
as an MCP server connected to Claude Code, orchestrating three agents —
Supervisor, Plan Agent, and Spec Writer — that hand off a single shared
state object in sequence, with every tool call traced.

## Goals (priority order)

1. **High accuracy** — specs must be complete, unambiguous, and grounded in
   actual project context, never guessed.
2. **Full traceability** — every tool call, state transition, and agent
   decision is logged to the CLI in real time.
3. **Minimum cost & latency** — avoid redundant LLM calls and repeated
   reads of the same file or resource.
4. **Strict sequential workflow** — no parallel/concurrent agent execution
   in v1. One agent runs at a time, in a fixed order.

## Tech stack

- **LangGraph** — orchestration graph for the Supervisor → Plan Agent →
  Spec Writer sequence and all state management between nodes.
- **LangChain** — agent construction (ReAct-pattern agents), tool binding,
  prompt templates.
- **FastMCP** — MCP server exposing SpecForge's tools and resources to
  Claude Code.
- **FastAPI** — optional HTTP interface for a tracing dashboard / debug
  endpoints (the MCP server itself uses stdio transport by default).
- **Pydantic** — schema definitions for `AgentState`, every tool's
  input/output, and hook payloads. All agent output is validated against a
  Pydantic model before it's accepted into state.
- **pytest** — unit tests per agent/tool, integration tests for full
  pipeline runs.

## Architecture

### Agents (all ReAct pattern)

Every agent runs a ReAct loop — Thought → Action → Observation, repeated —
with explicit chain-of-thought reasoning captured before each tool call.
Reasoning traces are logged by the pre-hook, never discarded.

- **Supervisor agent** — reads the project overview (this file) and
  gathers feature context: `feature_name`, `description`, `target_layer`,
  `data_source`, `user_facing`, `tech_stack`. Asks the user directly for
  any required field that's missing rather than assuming it. Hands off to
  the Plan Agent once state is complete.
- **Plan agent (sub-agent)** — receives state from the Supervisor, checks
  for an existing plan via `check_existing_plan`, proposes an
  implementation plan, and writes it via `write_plan_file` to
  `.claude/plans/[feature-name].md`. Updates state with `plan_path`.
- **Spec writer (sub-agent)** — receives state + plan, reads the plan via
  `read_plan_file`, and writes a spec-driven doc via `write_spec_file` to
  `.claude/spec/[feature-name].md`. Updates state with `spec_path` and
  reports the result back to the Supervisor.

### State

A single Pydantic model threaded through the entire LangGraph graph —
every node reads and writes to it directly; nothing is passed out-of-band.

```python
class AgentState(BaseModel):
    feature_name: str
    description: str
    target_layer: Literal["storefront", "backend", "admin", "file"]
    data_source: str
    user_facing: bool
    tech_stack: str
    plan_path: str | None = None
    spec_path: str | None = None
    status: Literal["gathering", "planning", "spec_writing", "done", "error"]
```

### Hooks

- **Pre-hook** (runs before every tool call) — logs the calling agent,
  the tool name, a snapshot of current state, and a status label
  (`reading_file`, `understanding`, `generating_plan`, `writing_spec`,
  `output`).
- **Post-hook** (runs after every agent's output) — validates the output
  against its expected Pydantic schema before it's accepted into state.
  On failure, halts the pipeline and surfaces the validation error instead
  of passing bad data downstream.

### Plugins

- **File I/O** — read/write access scoped to `.claude/plans/` and
  `.claude/spec/` only. No general filesystem access.

## Commands

- `pytest` — run all unit and integration tests
- `pytest tests/unit` — agent/tool-level tests only
- `pytest tests/integration` — full pipeline runs (mocked LLM calls)
- `python -m specforge.server` — start the MCP server (stdio transport)

## Conventions

- All agent outputs are Pydantic models — never raw strings passed
  between graph nodes.
- Every tool call goes through the traced wrapper — no direct,
  un-logged tool invocation anywhere in the codebase.
- No agent proceeds with a missing required state field — always ask the
  user, never assume or fill in a default silently.
- Cache file reads within a single run (e.g. `CLAUDE.md`, an existing
  plan file) so the same resource isn't re-fetched by multiple agents.
