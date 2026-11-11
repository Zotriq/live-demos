"""Cleaning, fingerprints and change detection."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from typing import Optional

from .models import Job

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")

# words that don't change what the job is
_TITLE_NOISE = {"m", "f", "d", "w", "x", "remote", "hybrid", "onsite", "on", "site", "the", "a", "an"}
_COMPANY_SUFFIX = {"inc", "llc", "ltd", "limited", "corp", "corporation", "co", "gmbh", "plc", "technologies", "technology"}

SALARY_RE = re.compile(
    r"(?:(?:US|CA|C)?\$|USD|CAD)\s?\d{2,3}(?:[,.]\d{3})*(?:\s?[kK])?"
    r"(?:\s?(?:-|–|to)\s?(?:(?:US|CA|C)?\$|USD|CAD)?\s?\d{2,3}(?:[,.]\d{3})*(?:\s?[kK])?)?"
)


def html_to_text(raw: Optional[str]) -> str:
    """Greenhouse double-encodes HTML (&amp;lt;p&amp;gt;), so unescape until stable."""
    if not raw:
        return ""
    text = raw
    for _ in range(3):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    text = re.sub(r"</(p|div|li|h\d|br)\s*>|<br\s*/?>", "\n", text, flags=re.I)
    text = _TAG.sub(" ", text)
    lines = [_WS.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _norm(text: str, drop: set[str] = frozenset()) -> str:
    text = _NON_ALNUM.sub(" ", (text or "").lower())
    words = [w for w in text.split() if w not in drop]
    return " ".join(words)


def norm_title(title: str) -> str:
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", title or "")      # "(Remote)", "[Canada]"
    t = t.replace("Sr.", "Senior").replace("Sr ", "Senior ").replace("Jr.", "Junior")
    return _norm(t, _TITLE_NOISE)


def norm_company(company: str) -> str:
    return _norm(company, _COMPANY_SUFFIX)


def norm_location(location: str) -> str:
    loc = _norm(location)
    if not loc or "remote" in loc or "anywhere" in loc:
        return "remote"
    return loc.split(" ")[0] if loc else ""                   # first city/region word is enough


def fingerprint(job: Job) -> str:
    """Same company + same role + same primary location = the same real job,
    even if it shows up on two different sources."""
    key = f"{norm_company(job.company)}|{norm_title(job.title)}|{norm_location(job.location)}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


TRACKED_FIELDS = ("title", "location", "salary", "url", "employment_type", "description")


def content_hash(job: Job) -> str:
    parts = [str(getattr(job, f) or "")[:4000] for f in TRACKED_FIELDS]
    return hashlib.sha1("\x1f".join(parts).encode()).hexdigest()[:16]


def find_salary(text: str) -> Optional[str]:
    m = SALARY_RE.search(text or "")
    return m.group(0).strip() if m else None


def parse_dt(value) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):                       # Lever: epoch ms
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def finalize(job: Job) -> Job:
    job.title = _WS.sub(" ", job.title or "").strip()
    job.company = _WS.sub(" ", job.company or "").strip()
    job.location = _WS.sub(" ", job.location or "").strip() or "Not specified"
    if not job.remote:
        job.remote = "remote" in (job.location + " " + job.title).lower()
    if not job.salary:
        job.salary = find_salary(job.description)
    job.fingerprint = fingerprint(job)
    job.content_hash = content_hash(job)
    return job
