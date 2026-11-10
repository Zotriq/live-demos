# Contributing

This is currently a personal portfolio project by Zohaib Tariq, but contributions,
issues, and suggestions are welcome.

## Development setup
1. Fork and clone the repository.
2. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in your own API keys.
5. Start PostgreSQL with pgvector: `docker compose up -d postgres`
6. Run the app: `uvicorn src.pdf_rag.main:app --reload`

## Code style
- Format with `black` and lint with `ruff`.
- Type hints are required on public functions.
- Keep modules single-responsibility (ingestion, retrieval, generation are separate layers).

## Tests
Run `pytest` before opening a pull request. New features require accompanying tests.

## Commit messages
Use conventional commits where possible, e.g. `feat: add pgvector reranking`.
