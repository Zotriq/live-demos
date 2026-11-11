"""Compliant job sources.

Every source here is a public, documented feed that companies or boards publish
for exactly this purpose. No LinkedIn / Indeed scraping.

- Greenhouse Job Board API: boards-api.greenhouse.io/v1/boards/{company}/jobs
- Lever Postings API:       api.lever.co/v0/postings/{company}?mode=json
- Ashby Posting API:        api.ashbyhq.com/posting-api/job-board/{company}
- Remotive API:             remotive.com/api/remote-jobs  (max ~4 calls/day, must credit Remotive)
- Sample:                   recorded snapshots for offline demos and tests
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import requests

from .models import Job
from .normalize import finalize, html_to_text, parse_dt

TIMEOUT = 20
HEADERS = {"User-Agent": "JobRadar/1.0 (job discovery demo)", "Accept": "application/json"}
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


class SourceError(Exception):
    pass


def _get(url: str, params: dict | None = None):
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise SourceError(f"network error: {exc.__class__.__name__}") from exc
    if resp.status_code == 404:
        raise SourceError("board not found (404) - check the company handle")
    if resp.status_code == 429:
        raise SourceError("rate limited (429) - try again later")
    if not resp.ok:
        raise SourceError(f"HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise SourceError("response was not JSON") from exc


def _pretty(handle: str) -> str:
    words = handle.replace("-", " ").replace("_", " ").split()
    return " ".join(w.upper() if w.lower() in {"ai", "io", "hq", "us", "uk"} else w.capitalize() for w in words)


# ---------------------------------------------------------------- parsers
# Parsers are separate from the HTTP call so tests and sample mode use the same code.

def parse_greenhouse(data: dict, board: str) -> list[Job]:
    jobs = []
    for j in data.get("jobs", []):
        offices = j.get("offices") or []
        depts = j.get("departments") or []
        jobs.append(Job(
            source="greenhouse",
            source_id=str(j.get("id")),
            board=board,
            title=j.get("title", ""),
            company=j.get("company_name") or _pretty(board),
            location=(j.get("location") or {}).get("name") or (offices[0].get("name") if offices else ""),
            url=j.get("absolute_url", ""),
            description=html_to_text(j.get("content")),
            department=depts[0].get("name") if depts else None,
            posted_at=parse_dt(j.get("first_published") or j.get("updated_at")),
        ))
    return jobs


def parse_lever(data: list, board: str) -> list[Job]:
    jobs = []
    for j in data or []:
        cats = j.get("categories") or {}
        salary = None
        sr = j.get("salaryRange") or {}
        if sr.get("min") and sr.get("max"):
            salary = f"{sr.get('currency', '')} {sr['min']:,}-{sr['max']:,}".strip()
        desc = j.get("descriptionPlain") or ""
        for lst in j.get("lists") or []:
            desc += "\n" + (lst.get("text") or "") + "\n" + html_to_text(lst.get("content"))
        jobs.append(Job(
            source="lever",
            source_id=str(j.get("id")),
            board=board,
            title=j.get("text", ""),
            company=_pretty(board),
            location=cats.get("location") or ", ".join(cats.get("allLocations") or []),
            url=j.get("hostedUrl") or j.get("applyUrl", ""),
            description=desc.strip(),
            salary=salary,
            employment_type=cats.get("commitment"),
            remote=(j.get("workplaceType") == "remote"),
            department=cats.get("team") or cats.get("department"),
            posted_at=parse_dt(j.get("createdAt")),
        ))
    return jobs


def parse_ashby(data: dict, board: str) -> list[Job]:
    jobs = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        comp = j.get("compensation") or {}
        jobs.append(Job(
            source="ashby",
            source_id=str(j.get("id") or j.get("jobUrl")),
            board=board,
            title=j.get("title", ""),
            company=_pretty(board),
            location=j.get("location") or "",
            url=j.get("jobUrl") or j.get("applyUrl", ""),
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            salary=comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary"),
            employment_type=j.get("employmentType"),
            remote=bool(j.get("isRemote")),
            department=j.get("department") or j.get("team"),
            posted_at=parse_dt(j.get("publishedAt")),
        ))
    return jobs


def parse_remotive(data: dict, board: str) -> list[Job]:
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("candidate_required_location") or "Worldwide"
        jobs.append(Job(
            source="remotive",
            source_id=str(j.get("id")),
            board=board,
            title=j.get("title", ""),
            company=j.get("company_name", ""),
            location=f"Remote ({loc})",
            url=j.get("url", ""),
            description=html_to_text(j.get("description")),
            salary=j.get("salary") or None,
            employment_type=(j.get("job_type") or "").replace("_", " ") or None,
            remote=True,
            department=j.get("category"),
            posted_at=parse_dt(j.get("publication_date")),
        ))
    return jobs


# ---------------------------------------------------------------- fetchers

def fetch_greenhouse(board: str) -> list[Job]:
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", {"content": "true"})
    return parse_greenhouse(data, board)


def fetch_lever(board: str) -> list[Job]:
    data = _get(f"https://api.lever.co/v0/postings/{board}", {"mode": "json"})
    return parse_lever(data, board)


def fetch_ashby(board: str) -> list[Job]:
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{board}", {"includeCompensation": "true"})
    return parse_ashby(data, board)


def fetch_remotive(search: str, limit: int = 50) -> list[Job]:
    data = _get("https://remotive.com/api/remote-jobs", {"search": search, "limit": limit})
    return parse_remotive(data, search)


def fetch_sample(snapshot: str) -> list[Job]:
    """Recorded responses in each source's real format, parsed by the real parsers."""
    path = SAMPLE_DIR / f"{snapshot}.json"
    if not path.exists():
        raise SourceError(f"sample snapshot '{snapshot}' not found")
    bundle = json.loads(path.read_text())
    jobs: list[Job] = []
    for board, payload in bundle.get("greenhouse", {}).items():
        jobs += parse_greenhouse(payload, board)
    for board, payload in bundle.get("lever", {}).items():
        jobs += parse_lever(payload, board)
    for board, payload in bundle.get("ashby", {}).items():
        jobs += parse_ashby(payload, board)
    for board, payload in bundle.get("remotive", {}).items():
        jobs += parse_remotive(payload, board)
    return jobs


# ---------------------------------------------------------------- plan

def plan(sources_cfg: dict, enabled: Iterable[str]) -> list[tuple[str, str, callable]]:
    """Turn the profile's source config into a list of (source, board, fetch_fn) tasks."""
    enabled = set(enabled)
    tasks = []
    for board in sources_cfg.get("greenhouse", []) if "greenhouse" in enabled else []:
        tasks.append(("greenhouse", board, lambda b=board: fetch_greenhouse(b)))
    for board in sources_cfg.get("lever", []) if "lever" in enabled else []:
        tasks.append(("lever", board, lambda b=board: fetch_lever(b)))
    for board in sources_cfg.get("ashby", []) if "ashby" in enabled else []:
        tasks.append(("ashby", board, lambda b=board: fetch_ashby(b)))
    if "remotive" in enabled:
        rcfg = sources_cfg.get("remotive", {}) or {}
        for term in rcfg.get("search", []):
            tasks.append(("remotive", term, lambda t=term, n=rcfg.get("limit", 50): fetch_remotive(t, n)))
    return tasks


def run_tasks(tasks, on_event=None, workers: int = 6) -> tuple[list[Job], list[str], set[tuple[str, str]]]:
    """Fetch every task in parallel; one failing board never stops the run.
    Events are emitted from the calling thread (Streamlit needs that)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    jobs, errors, ok = [], [], set()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(tasks) or 1))) as pool:
        futures = {pool.submit(fn): (source, board) for source, board, fn in tasks}
        for fut in as_completed(futures):
            source, board = futures[fut]
            try:
                got = [finalize(j) for j in fut.result()]
                jobs += got
                ok.add((source, board))
                if on_event:
                    on_event("fetch", f"{source}:{board} returned {len(got)} jobs")
            except SourceError as exc:
                errors.append(f"{source}:{board} - {exc}")
                if on_event:
                    on_event("error", f"{source}:{board} failed - {exc}")
            except Exception as exc:                          # noqa: BLE001 - parser surprise on a live feed
                errors.append(f"{source}:{board} - unexpected {exc.__class__.__name__}")
                if on_event:
                    on_event("error", f"{source}:{board} failed - unexpected {exc.__class__.__name__}")
    jobs.sort(key=lambda j: (j.source, j.board, j.source_id))   # stable order for dedup
    return jobs, errors, ok
