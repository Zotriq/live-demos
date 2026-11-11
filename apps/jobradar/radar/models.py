from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Job:
    """One job posting, normalised to the same shape whatever source it came from."""

    source: str                 # greenhouse | lever | ashby | remotive | sample
    source_id: str              # id inside that source
    board: str                  # company board / search term it came from
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    salary: Optional[str] = None
    employment_type: Optional[str] = None
    remote: bool = False
    department: Optional[str] = None
    posted_at: Optional[datetime] = None

    # filled by the pipeline
    fingerprint: str = ""
    content_hash: str = ""


@dataclass
class Score:
    score: int
    reason: str
    engine: str                 # "llm" | "rules"
    rule_score: int = 0
    matched_skills: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    run_id: int = 0
    fetched: int = 0
    new: int = 0
    duplicates: int = 0
    updated: int = 0
    closed: int = 0
    scored_llm: int = 0
    scored_rules: int = 0
    alerts: int = 0
    errors: list[str] = field(default_factory=list)
    new_job_ids: list[int] = field(default_factory=list)
    updated_job_ids: list[int] = field(default_factory=list)
    alerted_job_ids: list[int] = field(default_factory=list)
    duration_s: float = 0.0
