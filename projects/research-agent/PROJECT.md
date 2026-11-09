# Research Agent Project

## Project Overview

A modular, autonomous AI research agent that solves multi-hop questions by combining
real-time web search, local file ingestion, stateful hybrid memory, and real-time
execution logging. It ships with a **CLI** and a **Next.js chat UI** that renders the
same execution log live.

## Tech Stack

* **Language & Core Logic:** Python, Pydantic (tool arg schemas + event models)
* **LLM:** Groq — `openai/gpt-oss-120b` (reasoning) and `openai/gpt-oss-20b`
  (background summarisation), accessed through LangChain's `ChatGroq` **as the model
  client only**; the ReAct orchestration is hand-rolled (no `AgentExecutor` / LangGraph).
* **Search & Retrieval:** SerpAPI (Google engine). API keys are auto-detected from
  `.env` by value shape (`gsk_` ⇒ Groq), so a swapped `GROQ_API_KEY` / `SERP_API_KEY`
  still works.
* **File Processing:** PyMuPDF for PDF extraction, standard file I/O for text files,
  with a path-escape guard restricting reads to the project directory.
* **Memory & Orchestration:** In-memory only. Verbatim sliding window (last 5 turns)
  plus a rolling summary of older context produced by an automated background thread.
* **Observability:** One `ExecutionLogger` fans every event out to three sinks —
  colour-coded timestamped console stream, `agent_execution.log`, and an in-process
  queue that drives the Server-Sent-Events feed.
* **API & UI:** FastAPI (`POST /api/chat` SSE, `GET /api/health`) + a Next.js
  (App Router, TypeScript, TailwindCSS) two-pane app: chat thread on the left, live
  Thought / Action / Observation + tool-latency log on the right.

## Architecture & Workflow

1. **ReAct Paradigm:** A custom orchestrator (`agent/react_loop.py`) iterates through
   explicit `Thought` → `Action` → `Action Input` → `Observation` steps, capped at
   `MAX_ITERATIONS` (default 8). Malformed model output is fed back as an observation;
   once evidence is gathered, free-text output is accepted as the final answer.
2. **Tools & Plugins** (`agent/tools/`, Pydantic-validated, registered in `TOOL_REGISTRY`):
   * **web_search:** structured query to SerpAPI, returns answer box / knowledge graph
     / top organic results as compact text (timeout + one retry).
   * **file_read:** extracts text from `.txt` and `.pdf` (PyMuPDF), truncated, sandboxed
     to the project directory.
3. **Memory Management** (`agent/memory.py`): verbatim last-5 turns + a rolling summary;
   evicted turns are folded into the summary on a background thread using the cheap model.
4. **Execution Hooks** (`agent/logging_hooks.py`): every tool call is timed
   (`tool_latency` events) and every step is emitted as a structured `AgentEvent` to
   console, file, and SSE subscribers.

## Layout

```
agent/           core package (config, llm, prompts, parser, react_loop, memory,
                 events, logging_hooks, tools/)
server/app.py    FastAPI app exposing the agent over SSE
frontend/        Next.js + TypeScript + Tailwind chat + live-log UI
tests/           pytest: parser, memory (stub LLM), tools (SerpAPI fixture + tmp files)
```

## Running

```bash
pip install -r requirements.txt

# CLI — one-shot or interactive
python -m agent.cli "Who founded the company that makes the Ryzen CPU line, and what year was that person born?"
python -m agent.cli --repl

# API
uvicorn server.app:app --port 8000

# UI (separate terminal)
cd frontend && npm install && npm run dev   # http://localhost:3000

# Tests
pytest -q
```
