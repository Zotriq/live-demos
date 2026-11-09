# Live demos

Free, always-on demos of the projects on [zotriq.github.io](https://zotriq.github.io), hosted on Hugging Face Spaces.

Each folder in `spaces/` is one demo: a small Gradio app that imports the real code from the project's
own repository (cloned into `project/` at deploy time), so the demo runs the same logic as the repo.
AI demos use Groq's free tier through its OpenAI-compatible API.

On every push, `.github/workflows/deploy.yml` runs `deploy.py`, which creates or updates the Space,
copies the API key into the Space's secrets, waits for the build and calls each demo's endpoints with
sample inputs to check that it really works.
