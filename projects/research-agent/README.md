# Research Agent

Autonomous ReAct research agent: multi-hop reasoning over **web search** (SerpAPI) and
**local files** (`.txt` / `.pdf`), with hybrid in-memory conversation memory and a live,
colour-coded execution log. Ships with a CLI and a Next.js chat UI.

See [PROJECT.md](PROJECT.md) for the full architecture.

## Setup

```bash
pip install -r requirements.txt
```

`.env` needs a Groq key and a SerpAPI key:

```
GROQ_API_KEY = "gsk_..."
SERP_API_KEY = "..."
```

The two are auto-detected by shape, so it still works if the values are swapped.

## CLI

```bash
python -m agent.cli "What year was the founder of the company behind Ryzen born?"
python -m agent.cli --repl                 # interactive, memory persists across turns
python -m agent.cli --base-dir ./docs "Summarise report.pdf"
```

Every run also appends to `agent_execution.log`.

## API + UI

```bash
uvicorn server.app:app --port 8000        # POST /api/chat (SSE), GET /api/health
cd frontend && npm install && npm run dev # http://localhost:3000
```

The UI streams the agent's Thought / Action / Observation / latency events into the
right-hand panel while the answer lands in the chat thread on the left.

## Tests

```bash
pytest -q
```

## Configuration (env vars, all optional)

| Var | Default | Purpose |
|---|---|---|
| `MAIN_MODEL` | `openai/gpt-oss-120b` | reasoning model |
| `SUMMARY_MODEL` | `openai/gpt-oss-20b` | background summariser |
| `MAX_ITERATIONS` | `8` | ReAct step cap |
| `WINDOW_TURNS` | `5` | verbatim memory window |
| `SEARCH_RESULTS` | `5` | SerpAPI organic results kept |
| `FILE_READ_BASE_DIR` | project root | sandbox for `file_read` |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS allow-origin |
