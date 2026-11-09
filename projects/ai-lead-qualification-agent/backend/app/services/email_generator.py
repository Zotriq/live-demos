"""
Email Generator — Produce personalised follow-up emails for qualified leads.

Priority order:
  1. If the AI analysis already contains a well-formed follow_up_email, use it.
  2. Otherwise, fall back to a template that is parameterised by qualification
     status (hot / warm / cold / unqualified).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Typing aliases
# ---------------------------------------------------------------------------
EmailDict = dict[str, str]   # {"subject": "...", "body": "..."}


class EmailGenerator:
    """
    Generate a follow-up email for a lead.

    Usage
    -----
    gen = EmailGenerator()
    email = gen.generate_follow_up_email(lead_data, ai_analysis)
    # email = {"subject": "...", "body": "..."}
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_follow_up_email(
        self,
        lead_data: dict[str, Any],
        ai_analysis: dict[str, Any],
    ) -> EmailDict:
        """
        Return a follow-up email dict with ``subject`` and ``body`` keys.

        If the AI analysis produced a valid email, it is returned as-is.
        Otherwise a personalised template is rendered from the lead data.

        Parameters
        ----------
        lead_data:
            Raw lead fields.
        ai_analysis:
            Output from AILeadAnalyzer.analyze_lead().  Expected to
            contain a ``follow_up_email`` key and a ``qualification_status``
            key, but the method degrades gracefully if they are missing.

        Returns
        -------
        {"subject": str, "body": str}
        """
        # --- Prefer AI-generated email if it has real content ---
        ai_email = ai_analysis.get("follow_up_email")
        if self._is_valid_email(ai_email):
            logger.debug("Using AI-generated follow-up email.")
            return {
                "subject": str(ai_email["subject"]).strip(),
                "body": str(ai_email["body"]).strip(),
            }

        # --- Fall back to template ---
        logger.debug("Falling back to template-based follow-up email.")
        return self._render_template(lead_data, ai_analysis)

    # ------------------------------------------------------------------
    # Validation helper
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_email(email: Any) -> bool:
        """Return True only if the email dict has non-empty subject AND body."""
        if not isinstance(email, dict):
            return False
        subject = str(email.get("subject", "")).strip()
        body = str(email.get("body", "")).strip()
        return bool(subject) and bool(body) and len(body) > 20

    # ------------------------------------------------------------------
    # Template renderer
    # ------------------------------------------------------------------

    def _render_template(
        self,
        lead_data: dict[str, Any],
        ai_analysis: dict[str, Any],
    ) -> EmailDict:
        """Select and render the appropriate template for the lead's status."""
        # Pull personalisation tokens, defaulting gracefully.
        name = self._first_name(lead_data.get("name", ""))
        company = lead_data.get("company") or "your company"
        industry = lead_data.get("industry") or "your industry"
        budget = lead_data.get("budget")
        timeline = lead_data.get("timeline") or "your planned timeline"
        message_snippet = self._truncate(str(lead_data.get("message", "")), 120)

        status: str = (
            ai_analysis.get("qualification_status") or "cold"
        ).lower().strip()

        pain_points: list[str] = ai_analysis.get("pain_points") or []
        next_action: str = (
            ai_analysis.get("recommended_next_action") or "schedule a discovery call"
        )
        final_score: int = ai_analysis.get("final_score") or ai_analysis.get("lead_score") or 0

        context = dict(
            name=name,
            company=company,
            industry=industry,
            budget=budget,
            timeline=timeline,
            message_snippet=message_snippet,
            pain_points=pain_points,
            next_action=next_action,
            final_score=final_score,
        )

        if status == "hot":
            return self._hot_template(context)
        if status == "warm":
            return self._warm_template(context)
        if status == "cold":
            return self._cold_template(context)
        # unqualified or unknown
        return self._unqualified_template(context)

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    @staticmethod
    def _hot_template(ctx: dict[str, Any]) -> EmailDict:
        name = ctx["name"]
        company = ctx["company"]
        next_action = ctx["next_action"]
        pain_points_section = ""
        if ctx["pain_points"]:
            bullets = "\n".join(f"  • {p}" for p in ctx["pain_points"][:3])
            pain_points_section = (
                f"\nBased on what you shared, you're likely dealing with:\n{bullets}\n"
            )

        timeline_line = (
            f"Given your timeline of {ctx['timeline']}, "
            if ctx["timeline"] not in ("unknown", "your planned timeline", None, "")
            else ""
        )

        budget_line = ""
        if ctx["budget"] and str(ctx["budget"]).lower() not in ("unknown", ""):
            budget_line = (
                f"Your budget of {ctx['budget']} aligns well with what we offer. "
            )

        subject = f"Let's get started — your inquiry from {company}"

        body = (
            f"Hi {name},\n\n"
            f"Thank you for reaching out — your enquiry is exactly the kind of "
            f"challenge we help companies like {company} solve every day.\n"
            f"{pain_points_section}\n"
            f"{budget_line}"
            f"{timeline_line}we'd love to move quickly on this.\n\n"
            f"I'd like to {next_action}. Are you available for a 30-minute call "
            f"this week or early next week?\n\n"
            f"Please reply to this email or use the link below to book a time "
            f"that works for you.\n\n"
            f"Looking forward to connecting!\n\n"
            f"Best regards,\n"
            f"The Sales Team"
        )

        return {"subject": subject, "body": body}

    @staticmethod
    def _warm_template(ctx: dict[str, Any]) -> EmailDict:
        name = ctx["name"]
        company = ctx["company"]
        industry = ctx["industry"]
        next_action = ctx["next_action"]

        pain_points_section = ""
        if ctx["pain_points"]:
            bullets = "\n".join(f"  • {p}" for p in ctx["pain_points"][:2])
            pain_points_section = (
                f"\nYou mentioned challenges around:\n{bullets}\n"
                f"\nWe have helped similar businesses in {industry} address "
                f"exactly these pain points.\n"
            )

        subject = f"Following up on your inquiry — {company}"

        body = (
            f"Hi {name},\n\n"
            f"Thank you for your interest in our services. I have reviewed "
            f"your enquiry from {company} and believe there is a strong "
            f"potential fit.\n"
            f"{pain_points_section}\n"
            f"I would love to learn more about your specific situation and "
            f"explore how we might be able to help.\n\n"
            f"Would you be open to a brief 20-minute discovery call? "
            f"We can discuss your goals, share relevant case studies from "
            f"the {industry} sector, and outline what working together could "
            f"look like.\n\n"
            f"In the meantime, feel free to reply with any questions.\n\n"
            f"Best regards,\n"
            f"The Sales Team"
        )

        return {"subject": subject, "body": body}

    @staticmethod
    def _cold_template(ctx: dict[str, Any]) -> EmailDict:
        name = ctx["name"]
        company = ctx["company"]

        subject = f"Your inquiry — how we can help {company}"

        body = (
            f"Hi {name},\n\n"
            f"Thank you for getting in touch. We have received your enquiry "
            f"and wanted to follow up to make sure we fully understand your "
            f"needs.\n\n"
            f"Could you share a little more about:\n"
            f"  • The specific challenge you are trying to solve\n"
            f"  • Your expected timeline for implementing a solution\n"
            f"  • Your approximate budget range\n\n"
            f"This will help us tailor our response and ensure we recommend "
            f"the right solution for {company}.\n\n"
            f"We look forward to hearing from you.\n\n"
            f"Best regards,\n"
            f"The Sales Team"
        )

        return {"subject": subject, "body": body}

    @staticmethod
    def _unqualified_template(ctx: dict[str, Any]) -> EmailDict:
        name = ctx["name"]

        subject = "Thank you for reaching out"

        body = (
            f"Hi {name},\n\n"
            f"Thank you for contacting us. We appreciate you taking the time "
            f"to reach out.\n\n"
            f"We have reviewed your enquiry. At this time, we may not be the "
            f"best fit for your current needs — however, we would be happy to "
            f"point you in the right direction.\n\n"
            f"If your requirements change in the future, please do not "
            f"hesitate to get in touch. We are always happy to re-evaluate.\n\n"
            f"Best regards,\n"
            f"The Sales Team"
        )

        return {"subject": subject, "body": body}

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    @staticmethod
    def _first_name(full_name: str) -> str:
        """Extract first name or return a friendly fallback."""
        if not full_name or not full_name.strip():
            return "there"
        return full_name.strip().split()[0].capitalize()

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text to ``max_len`` characters, appending ellipsis if needed."""
        text = text.strip()
        if len(text) <= max_len:
            return text
        return text[:max_len].rstrip() + "…"
