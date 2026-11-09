"""Copy each project's code into projects/<repo>/ so the demos run the real thing.

    python sync_projects.py            # all
    python sync_projects.py sql-etl-pipeline

Streamlit Community Cloud only clones this repository, so the project code is
vendored here. Re-run after changing a project to pick up the new version.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent / "projects"
REPOS = [
    "ai-phishing-detector", "postgres-performance-tuning", "sql-etl-pipeline", "postgres-mcp-server",
    "invoice-extraction-pipeline", "langgraph-support-agents", "voice-ai-receptionist", "whatsapp-ai-agent",
    "stripe-crm-automation", "multitenant-rag-saas", "n8n-meeting-notes-to-clickup", "ai-lead-qualification-agent",
]
SKIP = {".git", ".github", "tests", "node_modules", "__pycache__", "docs", "datasets", ".gitignore", "LICENSE", "frontend"}

for repo in sys.argv[1:] or REPOS:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/Zotriq/{repo}", tmp], check=True)
        sha = subprocess.run(["git", "-C", tmp, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        dest = ROOT / repo
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(tmp, dest, ignore=lambda d, names: [n for n in names if n in SKIP or n.endswith(".ipynb")])
        (dest / "SOURCE").write_text(f"https://github.com/Zotriq/{repo} @ {sha}\n")
        print(f"{repo:32} {sha}")
