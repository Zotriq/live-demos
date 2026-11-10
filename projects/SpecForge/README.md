# SpecForge

Sequential multi-agent CLI tool that turns a one-line feature request
("I wanna build X") into a structured, spec-driven document.

**[Live demo →](https://zotriq-demos.streamlit.app/specforge)**

SpecForge runs as an MCP server connected to Claude Code and orchestrates
three agents that hand off a single shared state object in sequence, with
every tool call traced:

1. **Supervisor**: reads the project overview (`CLAUDE.md`) once, extracts the feature context
   (name, description, target layer, data source, user-facing, tech stack) and, if anything is
   missing, stops and returns questions instead of guessing.
2. **Plan Agent**: reuses an existing plan if there is one, otherwise writes
   `.claude/plans/<feature>.md` (Goal, Approach, Steps, Risks).
3. **Spec Writer**: reads the plan (from the run cache) and writes `.claude/spec/<feature>.md`
   (Overview, Requirements, Data model, Interfaces, Acceptance criteria, Out of scope).

Every file operation is a typed tool wrapped by `traced_tool` (pre-hook trace with agent, tool,
state snapshot and reasoning; input and output validated with Pydantic). Each agent's output passes a
post-hook schema check, and a bad output halts the pipeline instead of flowing downstream. File access
is scoped to `.claude/plans/` and `.claude/spec/`.

## Goals (priority order)

1. High accuracy — specs grounded in real project context, never guessed.
2. Full traceability — every tool call and state transition logged to the CLI in real time.
3. Minimum cost & latency — no redundant LLM calls or repeated file reads.
4. Strict sequential workflow — one agent at a time, fixed order, no concurrency in v1.

## Tech stack

| Concern | Library |
| --- | --- |
| Orchestration graph & state | LangGraph |
| Typed, traced tools (StructuredTool) | LangChain |
| LLM (any OpenAI-compatible API, Groq by default) | OpenAI SDK |
| MCP server (stdio transport) | FastMCP |
| Optional tracing dashboard / debug HTTP endpoints | FastAPI |
| Schemas & output validation | Pydantic |
| Tests | pytest |

## Getting started

```bash
py -m venv .venv
.venv\Scripts\activate           # Windows
pip install -e ".[dev]"
```

Set `GROQ_API_KEY` (or `SPECFORGE_API_KEY` with `SPECFORGE_BASE_URL` / `SPECFORGE_MODEL` for any
OpenAI-compatible endpoint; default model `openai/gpt-oss-120b` on Groq).

## Commands

- `python -m specforge "I wanna build a wishlist"`: run once from the terminal (asks for missing context)
- `python -m specforge.server`: start the MCP server (stdio); the `forge_spec(request, answers)` tool
- `pytest`: unit and integration tests (LLM calls faked, no keys needed)

Add it to Claude Code:

```bash
claude mcp add specforge -- python -m specforge.server
```

## Layout

```
specforge/
  server.py       FastMCP server entrypoint (stdio)
  state.py        AgentState Pydantic model
  graph.py        LangGraph graph: Supervisor -> Plan Agent -> Spec Writer
  config.py       Runtime settings
  agents/         ReAct agents: supervisor, plan_agent, spec_writer
  tools/          Traced tool wrapper + plan/spec file tools
  hooks/          Pre-hook (trace) and post-hook (schema validation)
  plugins/        Scoped file I/O (.claude/plans/, .claude/spec/ only)
  tracing/        Real-time CLI trace logger
  api/            Optional FastAPI debug/dashboard app
tests/
  unit/           Per agent/tool tests
  integration/    Full pipeline runs with mocked LLMs
plans/            Implementation planning docs (reviewed before build)
```

See [CLAUDE.md](CLAUDE.md) for the full architecture spec.
