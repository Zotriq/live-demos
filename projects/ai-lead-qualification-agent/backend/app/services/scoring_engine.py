"""
Scoring Engine — Rule-based lead qualification scoring.

Loads scoring rules from config/scoring_rules.yaml and evaluates
every inbound lead across budget, timeline, company size, decision-maker
authority, industry, country, intent, spam, and field completeness.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers to locate the YAML config regardless of working directory
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # .../services/
_CONFIG_PATH = _HERE.parent / "config" / "scoring_rules.yaml"


def _load_rules(path: Path = _CONFIG_PATH) -> dict:
    """Load and return the scoring rules from YAML."""
    if not path.exists():
        raise FileNotFoundError(f"Scoring rules not found at: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Company-size bucketing helper
# ---------------------------------------------------------------------------
def _bucket_company_size(size: int | str | None) -> str:
    """
    Map a numeric or string company size to a bucket name.

    Accepts integers, numeric strings, or pre-labelled strings
    (e.g. 'enterprise', '1-9', '500+').
    """
    if size is None:
        return "unknown"

    # If already a recognised label, pass it through.
    _labels = {"enterprise", "large", "medium", "small", "micro"}
    if isinstance(size, str) and size.lower() in _labels:
        return size.lower()

    # Try to parse a numeric value.
    try:
        numeric = int(str(size).replace(",", "").replace("+", "").split("-")[0].strip())
    except (ValueError, AttributeError):
        return "unknown"

    if numeric >= 500:
        return "enterprise"
    if numeric >= 200:
        return "large"
    if numeric >= 50:
        return "medium"
    if numeric >= 10:
        return "small"
    return "micro"


# ---------------------------------------------------------------------------
# Main scoring engine
# ---------------------------------------------------------------------------
class ScoringEngine:
    """
    Rule-based lead scoring engine.

    Usage
    -----
    engine = ScoringEngine()
    result = engine.score_lead(lead_data)
    # result = {
    #     "score": 82,
    #     "qualification_status": "hot",
    #     "breakdown": { ... }
    # }
    """

    def __init__(self, rules_path: Path | str | None = None) -> None:
        path = Path(rules_path) if rules_path else _CONFIG_PATH
        self.rules: dict = _load_rules(path)
        logger.info("ScoringEngine initialised with rules from %s", path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """
        Score a single lead and return a structured result.

        Parameters
        ----------
        lead_data:
            Dictionary of lead fields.  Recognised keys:

            - name (str)
            - email (str)
            - company (str)
            - phone (str)
            - budget (int | float | str)  — numeric USD value or label
            - timeline (str)              — e.g. 'asap', 'this_month', …
            - company_size (int | str)    — headcount or label
            - job_title (str)
            - industry (str)
            - country (str)
            - message (str)               — free-text description

        Returns
        -------
        {
            "score": int,                  # 0-100 (clamped)
            "qualification_status": str,   # hot | warm | cold | unqualified
            "breakdown": dict              # per-component scores
        }
        """
        breakdown: dict[str, int] = {}
        total = 0

        # 1. Budget
        budget_score = self._score_budget(lead_data.get("budget"))
        breakdown["budget"] = budget_score
        total += budget_score

        # 2. Timeline
        timeline_score = self._score_timeline(lead_data.get("timeline"))
        breakdown["timeline"] = timeline_score
        total += timeline_score

        # 3. Company size
        size_score = self._score_company_size(lead_data.get("company_size"))
        breakdown["company_size"] = size_score
        total += size_score

        # 4. Decision-maker authority
        dm_score = self._score_decision_maker(lead_data.get("job_title"))
        breakdown["decision_maker"] = dm_score
        total += dm_score

        # 5. Industry match
        industry_score = self._score_industry(lead_data.get("industry"))
        breakdown["industry_match"] = industry_score
        total += industry_score

        # 6. Country match
        country_score = self._score_country(lead_data.get("country"))
        breakdown["country_match"] = country_score
        total += country_score

        # 7. Intent detection (message text)
        intent_score = self._score_intent(lead_data.get("message", ""))
        breakdown["intent"] = intent_score
        total += intent_score

        # 8. Spam detection (message + name + company, etc.)
        full_text = " ".join(
            str(lead_data.get(f, ""))
            for f in ("name", "email", "company", "message", "job_title")
        )
        spam_penalty = self._score_spam(full_text)
        breakdown["spam_penalty"] = spam_penalty
        total += spam_penalty

        # 9. Field completeness
        completeness_score = self._score_completeness(lead_data)
        breakdown["completeness"] = completeness_score
        total += completeness_score

        # 10. Missing critical field penalties
        critical_penalties = self._score_missing_critical(lead_data)
        breakdown["missing_critical_penalties"] = critical_penalties
        total += critical_penalties

        # Clamp to [0, 100]
        final_score = max(0, min(100, total))
        breakdown["total_before_clamp"] = total
        breakdown["final_score"] = final_score

        status = self._qualify(final_score)

        return {
            "score": final_score,
            "qualification_status": status,
            "breakdown": breakdown,
        }

    # ------------------------------------------------------------------
    # Individual scoring components
    # ------------------------------------------------------------------

    def _score_budget(self, budget: Any) -> int:
        """
        Award points based on the declared budget value.

        - >= high_value_min  → 25 pts
        - >= medium_value_min → 15 pts
        - > 0                 → 5 pts
        - None / 0            → 0 pts
        """
        if budget is None:
            return 0

        # Attempt numeric conversion; strip currency symbols / commas.
        if isinstance(budget, str):
            cleaned = (
                budget.replace("$", "")
                .replace(",", "")
                .replace("£", "")
                .replace("€", "")
                .strip()
            )
            try:
                budget = float(cleaned)
            except ValueError:
                # Non-numeric label — try known labels
                label = budget.lower()
                if label in ("high", "enterprise", "large"):
                    budget = self.rules["budget"]["high_value_min"]
                elif label in ("medium", "mid"):
                    budget = self.rules["budget"]["medium_value_min"]
                else:
                    return 0

        try:
            amount = float(budget)
        except (TypeError, ValueError):
            return 0

        high_min = self.rules["budget"]["high_value_min"]
        med_min = self.rules["budget"]["medium_value_min"]

        if amount >= high_min:
            return 25
        if amount >= med_min:
            return 15
        if amount > 0:
            return 5
        return 0

    def _score_timeline(self, timeline: Any) -> int:
        """Map timeline string to points using YAML lookup table."""
        if not timeline:
            return self.rules["timeline_scores"].get("unknown", 0)

        key = str(timeline).lower().strip().replace(" ", "_")
        scores: dict = self.rules["timeline_scores"]

        # Direct match
        if key in scores:
            return scores[key]

        # Fuzzy fallbacks
        raw = str(timeline).lower().strip()
        if raw in ("now", "immediately", "urgent"):
            return scores.get("asap", 20)
        if "month" in raw and ("this" in raw or "1" in raw):
            return scores.get("this_month", 20)
        if "next month" in raw or "30 day" in raw:
            return scores.get("next_month", 10)
        if "quarter" in raw and ("this" in raw or "current" in raw):
            return scores.get("this_quarter", 5)
        if "next quarter" in raw or "q+" in raw:
            return scores.get("next_quarter", 2)

        return scores.get("unknown", 0)

    def _score_company_size(self, company_size: Any) -> int:
        """Award points based on bucketed company headcount."""
        bucket = _bucket_company_size(company_size)
        return self.rules["company_size_scores"].get(bucket, 0)

    def _score_decision_maker(self, job_title: Any) -> int:
        """Award points if job title matches decision-maker keywords."""
        if not job_title:
            return 0

        title_lower = str(job_title).lower()
        dm_titles: list[str] = self.rules["decision_maker_titles"]

        for keyword in dm_titles:
            if keyword.lower() in title_lower:
                return self.rules["decision_maker_score"]

        return 0

    def _score_industry(self, industry: Any) -> int:
        """Award points if industry matches a target sector."""
        if not industry:
            return 0

        industry_lower = str(industry).lower()
        for target in self.rules["target_industries"]:
            if target.lower() in industry_lower or industry_lower in target.lower():
                return self.rules["industry_match_score"]

        return 0

    def _score_country(self, country: Any) -> int:
        """Award points if country is in the target list."""
        if not country:
            return 0

        country_lower = str(country).lower().strip()
        for target in self.rules["target_countries"]:
            if target.lower() == country_lower:
                return self.rules["country_match_score"]

        return 0

    def _score_intent(self, message: Any) -> int:
        """
        Award intent points if any intent keyword appears in the message.
        Points are awarded once (not stacked) to avoid gaming.
        """
        if not message:
            return 0

        message_lower = str(message).lower()
        for keyword in self.rules["intent_keywords"]:
            if keyword.lower() in message_lower:
                return self.rules["intent_score"]

        return 0

    def _score_spam(self, text: Any) -> int:
        """
        Apply spam penalty if any spam keyword is detected in combined text.
        Returns a *negative* integer or 0.
        """
        if not text:
            return 0

        text_lower = str(text).lower()
        for keyword in self.rules["spam_keywords"]:
            if keyword.lower() in text_lower:
                logger.warning("Spam keyword detected: '%s'", keyword)
                return self.rules["spam_penalty"]  # already negative in YAML

        return 0

    def _score_completeness(self, lead_data: dict[str, Any]) -> int:
        """
        Award proportional completeness points based on how many
        tracked fields are present and non-empty.
        """
        fields: list[str] = self.rules["completeness_fields"]
        max_score: int = self.rules["completeness_max_score"]

        if not fields:
            return 0

        filled = sum(
            1
            for f in fields
            if lead_data.get(f) not in (None, "", 0)
        )

        ratio = filled / len(fields)
        return round(ratio * max_score)

    def _score_missing_critical(self, lead_data: dict[str, Any]) -> int:
        """
        Apply penalties for missing critical fields.
        Returns a *negative* integer or 0.
        """
        penalties: dict[str, int] = self.rules["missing_critical_penalties"]
        total_penalty = 0

        for field, penalty in penalties.items():
            value = lead_data.get(field)
            if value in (None, "", 0):
                total_penalty += penalty  # penalty values are negative in YAML

        return total_penalty

    # ------------------------------------------------------------------
    # Qualification status mapping
    # ------------------------------------------------------------------

    def _qualify(self, score: int) -> str:
        """Map a numeric score to a qualification bucket."""
        thresholds: dict = self.rules["thresholds"]
        if score >= thresholds["hot"]:
            return "hot"
        if score >= thresholds["warm"]:
            return "warm"
        if score >= thresholds["cold"]:
            return "cold"
        return "unqualified"
