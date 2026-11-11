"""Relevance scoring in two stages.

1. Rules (free, instant): title, skills, location, seniority. Obvious misses stop here.
2. LLM (only for jobs that pass the rules): a 0-100 score with a one-line reason.

Any OpenAI-compatible API works: Groq (default), OpenAI, or a local model server.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

import requests

from .models import Job, Score

SENIORITY_WORDS = {
    "intern": ["intern", "internship", "co-op", "coop", "student"],
    "junior": ["junior", "jr", "entry level", "new grad", "graduate", "associate"],
    "mid": [],
    "senior": ["senior", "sr", "staff", "lead"],
    "principal": ["principal", "distinguished", "director", "head of", "vp", "vice president"],
}


def detect_seniority(title: str) -> str:
    t = f" {title.lower()} "
    for level in ("intern", "principal", "senior", "junior"):
        if any(re.search(rf"\b{re.escape(w)}\b", t) for w in SENIORITY_WORDS[level]):
            return level
    return "mid"


def _has(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text) is not None


class RuleScorer:
    def __init__(self, profile: dict):
        self.p = profile

    def score(self, job: Job) -> Score:
        title = job.title.lower()
        body = f"{title}\n{job.description.lower()[:6000]}"
        loc = f"{job.location} {'remote' if job.remote else ''}".lower()
        reasons, pts = [], 0

        for term in self.p.get("exclude_title_terms", []):
            if _has(title, term):
                return Score(0, f"Excluded: title contains '{term}'", "rules", 0)

        # title (max 40)
        best = 0
        role_noun = re.search(r"engineer|developer|architect|\bsre\b|reliability", title) is not None
        for target in self.p.get("titles", []):
            words = [w for w in re.findall(r"[a-z0-9+#]+", target.lower()) if w not in {"engineer", "developer", "specialist"}]
            if _has(title, target):
                best = 40
                break
            if words and role_noun and all(_has(title, w) for w in words):
                best = max(best, 34)
            elif words and role_noun and any(_has(title, w) for w in words):
                best = max(best, 20)
        pts += best
        if best >= 34:
            reasons.append("title matches")
        elif best:
            reasons.append("related title")

        # skills (max 25)
        matched = [s for s in self.p.get("skills", []) if _has(body, s)]
        pts += min(25, 5 * len(matched))
        if matched:
            reasons.append(f"skills: {', '.join(matched[:4])}")

        # location (max 20)
        wanted = [w.lower() for w in self.p.get("locations", [])]
        if any(w != "remote" and w in loc for w in wanted):
            pts += 20
            reasons.append("location fits")
        elif "remote" in wanted and job.remote:
            restricted = re.search(r"\((.*?)\)", job.location)
            region = restricted.group(1).lower() if restricted else ""
            if not region or any(k in region for k in ("worldwide", "anywhere", "global")) or any(w in region for w in wanted):
                pts += 18
                reasons.append("remote")
            else:
                pts -= 10
                reasons.append(f"remote but limited to {restricted.group(1)}")

        # seniority (+10 / -20)
        level = detect_seniority(job.title)
        allowed = [s.lower() for s in self.p.get("seniority", [])]
        if not allowed or level in allowed:
            pts += 10
        elif level in ("intern", "principal") or (level == "junior" and "junior" not in allowed):
            pts -= 20
            reasons.append(f"seniority: {level}")

        pts = max(0, min(100, pts))
        return Score(pts, "; ".join(reasons) or "no match", "rules", pts, matched)


SYSTEM = (
    "You score job postings for a recruitment agency. Compare the job to the search profile "
    "and return ONLY JSON: {\"score\": 0-100, \"reason\": \"max 18 words, specific\", "
    "\"skills_matched\": [\"...\"]}. 85+ = strong fit on role, skills, level and location. "
    "60-84 = good fit with one gap. 40-59 = partial. Below 40 = poor fit. Be strict and consistent."
)


class LLMScorer:
    def __init__(self, profile: dict):
        self.p = profile
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        if os.getenv("LLM_BASE_URL"):
            self.base_url = os.getenv("LLM_BASE_URL").rstrip("/")
        elif os.getenv("GROQ_API_KEY") or (os.getenv("LLM_API_KEY") and not os.getenv("OPENAI_API_KEY")):
            self.base_url = "https://api.groq.com/openai/v1"
        else:
            self.base_url = "https://api.openai.com/v1"
        default_model = "openai/gpt-oss-20b" if "groq" in self.base_url else "gpt-4o-mini"
        self.model = os.getenv("LLM_MODEL", default_model)
        self._json_mode = True

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def label(self) -> str:
        host = re.sub(r"^https?://(api\.)?", "", self.base_url).split("/")[0]
        return f"{self.model} via {host}"

    def _profile_text(self) -> str:
        p = self.p
        return (f"Target titles: {', '.join(p.get('titles', []))}\n"
                f"Key skills: {', '.join(p.get('skills', []))}\n"
                f"Locations: {', '.join(p.get('locations', []))}\n"
                f"Seniority: {', '.join(p.get('seniority', [])) or 'any'}\n"
                f"Notes: {p.get('notes', '')}")

    def score(self, job: Job, rule: Score) -> Optional[Score]:
        user = (f"SEARCH PROFILE\n{self._profile_text()}\n\nJOB\nTitle: {job.title}\nCompany: {job.company}\n"
                f"Location: {job.location}\nSalary: {job.salary or 'not stated'}\n"
                f"Description:\n{job.description[:3500]}")
        body = {"model": self.model, "temperature": 0,
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=body, timeout=45,
                              headers={"Authorization": f"Bearer {self.api_key}"})
            if r.status_code == 400 and self._json_mode:      # model without JSON mode: retry plain
                self._json_mode = False
                return self.score(job, rule)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"] or ""
            m = re.search(r"\{.*\}", text, re.S)
            data = json.loads(m.group(0) if m else text)
            s = int(max(0, min(100, round(float(data["score"])))))
            reason = str(data.get("reason", "")).strip()[:220] or rule.reason
            skills = [str(x) for x in (data.get("skills_matched") or rule.matched_skills)][:8]
            return Score(s, reason, "llm", rule.rule_score, skills)
        except Exception:                                     # noqa: BLE001 - never break a run on one job
            return None


class HybridScorer:
    def __init__(self, profile: dict, use_llm: bool = True):
        self.rules = RuleScorer(profile)
        self.llm = LLMScorer(profile)
        self.use_llm = use_llm and self.llm.enabled
        self.prefilter = int(profile.get("llm_prefilter", 35))
        self.max_llm = int(profile.get("max_llm_calls_per_run", 40))
        self.llm_calls = 0

    def score(self, job: Job) -> Score:
        rule = self.rules.score(job)
        if not self.use_llm or rule.score < self.prefilter or self.llm_calls >= self.max_llm:
            return rule
        self.llm_calls += 1
        return self.llm.score(job, rule) or rule
