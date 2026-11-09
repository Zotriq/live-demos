"""Deploy demos in spaces/ to Hugging Face Spaces and smoke-test them.

    python deploy.py                  # every space
    python deploy.py phishing-detector postgres-tuning

Each spaces/<name>/ folder holds app.py, requirements.txt and space.json. The space
is staged with shared/ and a copy of the source repo (space.json "source") in project/,
uploaded, then the script waits for the build and calls the endpoints listed under
"smoke" with gradio_client. Needs HF_TOKEN; secrets listed in space.json are copied
from the environment into the Space settings.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from huggingface_hub import HfApi

ROOT = Path(__file__).parent
GRADIO_VERSION = "6.29.1"
api = HfApi(token=os.environ["HF_TOKEN"])
USER = api.whoami()["name"]
results: list[tuple[str, str, str]] = []


def space_host(name: str) -> str:
    return f"https://{USER.lower()}-{name.lower()}.hf.space".replace("_", "-")


def stage(name: str, cfg: dict, out: Path) -> None:
    src = ROOT / "spaces" / name
    shutil.copytree(src, out, ignore=shutil.ignore_patterns("project", "shared", "space.json", "__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "shared", out / "shared", ignore=shutil.ignore_patterns("__pycache__"))
    if cfg.get("source"):
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{cfg['source']}", str(out / "project")], check=True)
        shutil.rmtree(out / "project" / ".git")
        for pattern in cfg.get("exclude", []):
            for p in (out / "project").glob(pattern):
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    meta = {
        "title": cfg["title"], "emoji": cfg.get("emoji", "⚙️"), "colorFrom": "green", "colorTo": "gray",
        "sdk": "gradio", "sdk_version": GRADIO_VERSION, "app_file": "app.py", "pinned": False,
        "license": "mit", "short_description": cfg["short_description"][:60],
    }
    front = "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items())
    code = f"https://github.com/{cfg['source']}" if cfg.get("source") else "https://github.com/Zotriq/live-demos"
    (out / "README.md").write_text(
        f"---\n{front}\n---\n\n# {cfg['title']}\n\n{cfg['short_description']}.\n\n"
        f"Code: {code} · Portfolio: https://zotriq.github.io · Built by Zohaib Tariq\n"
    )


def wait_running(repo: str, timeout: int = 1500) -> str:
    start, stage_ = time.time(), ""
    time.sleep(20)
    while time.time() - start < timeout:
        stage_ = api.get_space_runtime(repo).stage
        if stage_ in ("RUNNING", "BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "NO_APP_FILE"):
            return stage_
        time.sleep(15)
    return f"TIMEOUT ({stage_})"


def print_logs(repo: str, kind: str, lines: int = 80) -> None:
    url = f"https://huggingface.co/api/spaces/{repo}/logs/{kind}"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"}, stream=True, timeout=20)
        out = []
        start = time.time()
        for raw in r.iter_lines():
            if time.time() - start > 15:
                break
            if raw.startswith(b"data: "):
                try:
                    out.append(json.loads(raw[6:]).get("data", "").rstrip())
                except ValueError:
                    pass
        print(f"----- last {kind} log lines -----")
        print("\n".join(out[-lines:]))
    except Exception as exc:  # logs are best effort
        print(f"(could not read {kind} logs: {exc})")


def smoke(name: str, cfg: dict) -> str:
    from gradio_client import Client

    client = Client(space_host(name) + "/", verbose=False)
    fails = []
    for case in cfg.get("smoke", []):
        try:
            out = client.predict(*case["args"], api_name=case["api_name"])
            text = json.dumps(out, ensure_ascii=False, default=str) if not isinstance(out, str) else out
            ok = case.get("expect", "") in text
            print(f"  {'PASS' if ok else 'FAIL'} {case['api_name']}: {text[:300]}")
            if not ok:
                fails.append(case["api_name"])
        except Exception as exc:
            print(f"  FAIL {case['api_name']}: {exc}")
            fails.append(case["api_name"])
    return "ok" if not fails else "smoke failed: " + ", ".join(fails)


def deploy(name: str) -> None:
    cfg = json.loads((ROOT / "spaces" / name / "space.json").read_text())
    repo = f"{USER}/{name}"
    print(f"\n===== {repo} =====")
    api.create_repo(repo, repo_type="space", space_sdk="gradio", exist_ok=True, private=False)
    for key in cfg.get("secrets", []):
        if os.environ.get(key):
            api.add_space_secret(repo, key, os.environ[key])
    for key, value in cfg.get("variables", {}).items():
        api.add_space_variable(repo, key, value)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / name
        stage(name, cfg, out)
        api.upload_folder(folder_path=str(out), repo_id=repo, repo_type="space",
                          commit_message="Deploy from Zotriq/live-demos", delete_patterns=["*"])
    status = wait_running(repo)
    print(f"status: {status}")
    if status != "RUNNING":
        print_logs(repo, "build")
        print_logs(repo, "run")
        results.append((name, status, space_host(name)))
        return
    time.sleep(10)
    outcome = smoke(name, cfg)
    if outcome != "ok":
        print_logs(repo, "run", 40)
    results.append((name, outcome, space_host(name)))


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(p.name for p in (ROOT / "spaces").iterdir() if (p / "space.json").exists())
    print(f"Hugging Face user: {USER}")
    if os.environ.get("GROQ_API_KEY"):
        r = requests.get("https://api.groq.com/openai/v1/models",
                         headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}, timeout=20)
        print("Groq key:", "valid" if r.ok else f"ERROR {r.status_code}",
              "| models:", ", ".join(sorted(m["id"] for m in r.json().get("data", []))) if r.ok else "")
    for n in names:
        try:
            deploy(n)
        except Exception as exc:
            print(f"deploy {n} crashed: {exc}")
            results.append((n, f"crashed: {exc}", space_host(n)))
    print("\n===== SUMMARY =====")
    for n, s, url in results:
        print(f"{n:32} {s:24} {url}")
    sys.exit(0 if all(s == "ok" for _, s, _ in results) else 1)
