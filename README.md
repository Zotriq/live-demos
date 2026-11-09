# Live demos

Working demos of the projects on [zotriq.github.io](https://zotriq.github.io), in one free
[Streamlit Community Cloud](https://streamlit.io/cloud) app. Each demo is a page with its own URL.

- **The real code.** `projects/` holds a copy of each project's repository (`python sync_projects.py`
  refreshes it), and every page imports it instead of re-implementing it.
- **Real AI.** AI demos call open models on Groq's free tier through its OpenAI-compatible API, using
  the projects' own OpenAI clients pointed at a different base URL.
- **Real databases.** Database demos start a throwaway PostgreSQL server inside the app, installed with
  pip (`postgresql-binaries` for PostgreSQL 18 with contrib, `pixeltable-pgserver` for pgvector).

Run locally (Python 3.12, as a non-root user, because PostgreSQL refuses to run as root):

```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...   # or put it in .streamlit/secrets.toml
streamlit run streamlit_app.py
```
