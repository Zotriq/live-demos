# Contributing to AI Lead Qualification Agent

Thank you for your interest in contributing! This guide will help you get started.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork locally
3. **Create a branch** for your feature or fix
4. **Make your changes** with clear, descriptive commits
5. **Test** your changes locally
6. **Push** to your fork and submit a **Pull Request**

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- OpenAI API key

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
# Edit .env with your settings
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker (Full Stack)

```bash
cp .env.example .env
docker compose up --build
```

## Code Style

### Python (Backend)
- Follow PEP 8
- Use type hints
- Keep functions focused and small
- Write docstrings for public functions

### TypeScript (Frontend)
- Use TypeScript strict mode
- Prefer functional components with hooks
- Use Tailwind CSS for styling
- Keep components small and reusable

## Pull Request Guidelines

- Keep PRs focused on a single change
- Include a clear description of what and why
- Reference related issues (e.g., "Closes #12")
- Ensure no linting errors
- Test both backend and frontend if changes span both
- Update documentation if needed

## Commit Messages

Use clear, descriptive commit messages:

```
feat: add calendar booking integration
fix: resolve lead scoring edge case for missing budget
docs: update API reference with new endpoints
refactor: extract email template logic into service
```

Prefixes: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`

## Reporting Issues

- Use the issue templates when available
- Include steps to reproduce for bugs
- Include expected vs actual behavior
- Add screenshots for UI issues
- Mention your environment (OS, Python/Node version, Docker)

## Areas for Contribution

Check out our [open issues](https://github.com/Zotriq/ai-lead-qualification-agent/issues) for areas where help is needed. Issues labeled `good first issue` are great starting points.

Key areas:
- **Integrations** — New CRM/tool integrations
- **Scoring** — Improved scoring algorithms
- **Frontend** — Dashboard UI improvements
- **Testing** — Unit and integration tests
- **Documentation** — Guides, tutorials, examples
- **DevOps** — CI/CD, deployment configs

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
