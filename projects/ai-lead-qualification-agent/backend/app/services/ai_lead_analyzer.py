"""
AI Lead Analyzer — OpenAI-powered lead analysis with rule-based fallback.

Sends structured lead data to GPT and merges the AI score with the
rule-based score (60 % AI + 40 % rules) to produce a final assessment.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are an AI sales qualification assistant. "
    "Analyze inbound leads using only the provided lead information. "
    "Do not invent facts. If information is missing, use 'unknown'. "
    "Score the lead from 0 to 100 based on fit, budget, urgency, authority, "
    "intent, and completeness. "
    "Classify the lead as hot, warm, cold, or unqualified. "
    "Generate a concise recommended next action and a personalized follow-up "
    "email draft. "
    "Always return valid JSON matching the requested schema."
)

# ---------------------------------------------------------------------------
# Expected JSON schema (sent to the model so it stays on target)
# ---------------------------------------------------------------------------
_RESPONSE_SCHEMA = {
    "lead_score": "integer 0-100",
    "qualification_status": "hot | warm | cold | unqualified",
    "intent_level": "high | medium | low | unknown",
    "budget_fit": "excellent | good | moderate | poor | unknown",
    "urgency": "immediate | short_term | medium_term | long_term | unknown",
    "industry_fit": "strong | moderate | weak | unknown",
    "decision_maker_likelihood": "high | medium | low | unknown",
    "pain_points": ["string"],
    "recommended_next_action": "string",
    "reasoning": "string",
    "risks_or_missing_info": ["string"],
    "follow_up_email": {
        "subject": "string",
        "body": "string",
    },
}

# ---------------------------------------------------------------------------
# Score blending weights
# ---------------------------------------------------------------------------
AI_WEIGHT = 0.60
RULE_WEIGHT = 0.40


class AILeadAnalyzer:
    """
    Async lead analyzer that calls OpenAI and blends the result with the
    rule-based score.

    Usage
    -----
    analyzer = AILeadAnalyzer()
    result = await analyzer.analyze_lead(lead_data, rule_score=72)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> None:
        resolved_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            logger.warning(
                "OPENAI_API_KEY is not set — AI analysis will use fallback mode."
            )
            self._client = None
        else:
            self._client = AsyncOpenAI(api_key=resolved_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze_lead(
        self,
        lead_data: dict[str, Any],
        rule_score: int,
    ) -> dict[str, Any]:
        """
        Analyze a lead with OpenAI and blend the result with the rule score.

        Parameters
        ----------
        lead_data:
            Raw lead fields as a dictionary.
        rule_score:
            The score produced by ScoringEngine (0–100).

        Returns
        -------
        Extended analysis dict containing all response schema fields plus:
        - ``rule_score``   — original rule-based score
        - ``ai_score``     — raw AI score (or rule_score on fallback)
        - ``final_score``  — blended 60 % AI + 40 % rule score
        - ``ai_available`` — whether OpenAI was actually called
        """
        try:
            raw_response = await self._call_openai(lead_data, rule_score)
            analysis = self._parse_response(raw_response)
            analysis["ai_available"] = True
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "OpenAI analysis failed (%s: %s) — using rule-based fallback.",
                type(exc).__name__,
                exc,
            )
            analysis = self._build_fallback(lead_data, rule_score)
            analysis["ai_available"] = False

        # Blend scores
        ai_score: int = int(analysis.get("lead_score") or rule_score)
        final_score = self._blend_scores(ai_score, rule_score)

        analysis["rule_score"] = rule_score
        analysis["ai_score"] = ai_score
        analysis["final_score"] = final_score
        # Override lead_score with the blended value for downstream consumers.
        analysis["lead_score"] = final_score

        # Derive qualification status from blended score if AI was unavailable.
        if not analysis.get("ai_available"):
            analysis["qualification_status"] = _qualify_from_score(final_score)

        return analysis

    # ------------------------------------------------------------------
    # OpenAI call
    # ------------------------------------------------------------------

    async def _call_openai(
        self,
        lead_data: dict[str, Any],
        rule_score: int,
    ) -> str:
        """Send the analysis request to OpenAI and return the raw text."""
        if self._client is None:
            raise RuntimeError("OpenAI client is not configured (no API key).")

        user_prompt = self._build_user_prompt(lead_data, rule_score)

        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            max_completion_tokens=self._max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned an empty response.")
        return content

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(lead_data: dict[str, Any], rule_score: int) -> str:
        """
        Compose the user-facing prompt.

        The rule-based score is included so the model has quantitative
        context without overriding its own judgment.
        """
        fields = [
            ("Name", lead_data.get("name", "unknown")),
            ("Email", lead_data.get("email", "unknown")),
            ("Company", lead_data.get("company", "unknown")),
            ("Phone", lead_data.get("phone", "unknown")),
            ("Job Title", lead_data.get("job_title", "unknown")),
            ("Industry", lead_data.get("industry", "unknown")),
            ("Country", lead_data.get("country", "unknown")),
            ("Company Size", lead_data.get("company_size", "unknown")),
            ("Budget (USD)", lead_data.get("budget", "unknown")),
            ("Timeline", lead_data.get("timeline", "unknown")),
            ("Message", lead_data.get("message", "unknown")),
            ("Source", lead_data.get("source", "unknown")),
            ("Website", lead_data.get("website", "unknown")),
        ]

        lines = ["## Lead Information\n"]
        for label, value in fields:
            lines.append(f"- **{label}**: {value}")

        lines.append(f"\n## Rule-Based Score (for context only): {rule_score}/100")
        lines.append(
            "\nPlease analyze this lead and return a JSON object that strictly "
            "conforms to the following schema:\n"
        )
        lines.append(json.dumps(_RESPONSE_SCHEMA, indent=2))
        lines.append(
            "\nEnsure all fields are present. Use 'unknown' for any field you "
            "cannot confidently assess. Keep reasoning under 150 words. "
            "The follow_up_email body should be professional, concise, and "
            "personalised to the lead's specific context."
        )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw: str) -> dict[str, Any]:
        """Parse and lightly validate the JSON response from OpenAI."""
        try:
            data: dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            # Attempt to extract JSON object from surrounding text.
            import re

            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError(f"Could not parse JSON from OpenAI response: {exc}") from exc

        # Ensure list fields are actually lists.
        for list_field in ("pain_points", "risks_or_missing_info"):
            if not isinstance(data.get(list_field), list):
                data[list_field] = []

        # Ensure follow_up_email is a dict.
        if not isinstance(data.get("follow_up_email"), dict):
            data["follow_up_email"] = {"subject": "", "body": ""}

        # Clamp lead_score to [0, 100].
        try:
            data["lead_score"] = max(0, min(100, int(data.get("lead_score", 0))))
        except (TypeError, ValueError):
            data["lead_score"] = 0

        return data

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fallback(lead_data: dict[str, Any], rule_score: int) -> dict[str, Any]:
        """
        Return a minimal analysis dict built purely from the rule score.
        Used when OpenAI is unavailable.
        """
        status = _qualify_from_score(rule_score)
        name = lead_data.get("name", "there")
        company = lead_data.get("company", "your company")

        return {
            "lead_score": rule_score,
            "qualification_status": status,
            "intent_level": "unknown",
            "budget_fit": "unknown",
            "urgency": "unknown",
            "industry_fit": "unknown",
            "decision_maker_likelihood": "unknown",
            "pain_points": [],
            "recommended_next_action": (
                "Review lead manually — AI analysis was unavailable at this time."
            ),
            "reasoning": (
                f"AI analysis could not be completed. "
                f"Rule-based score of {rule_score}/100 indicates a "
                f"'{status}' lead classification."
            ),
            "risks_or_missing_info": [
                "AI analysis unavailable — manual review recommended."
            ],
            "follow_up_email": {
                "subject": f"Following up on your inquiry, {name}",
                "body": (
                    f"Hi {name},\n\n"
                    f"Thank you for reaching out about {company}. "
                    "We have received your inquiry and a member of our team "
                    "will be in touch shortly.\n\n"
                    "Best regards,\nThe Sales Team"
                ),
            },
        }

    # ------------------------------------------------------------------
    # Score blending
    # ------------------------------------------------------------------

    @staticmethod
    def _blend_scores(ai_score: int, rule_score: int) -> int:
        """Return the weighted blend of AI and rule scores, clamped to [0, 100]."""
        blended = (AI_WEIGHT * ai_score) + (RULE_WEIGHT * rule_score)
        return max(0, min(100, round(blended)))


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

def _qualify_from_score(score: int) -> str:
    """Derive a qualification label from a numeric score using fixed thresholds."""
    if score >= 75:
        return "hot"
    if score >= 50:
        return "warm"
    if score >= 25:
        return "cold"
    return "unqualified"
