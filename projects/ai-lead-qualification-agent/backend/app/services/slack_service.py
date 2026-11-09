"""
Slack notification service.

Sends richly formatted Slack messages via an Incoming Webhook URL.
The integration is opt-in: if SLACK_WEBHOOK_URL is not set, every call
logs a warning and returns False / a skipped status.

Dependencies:
    pip install httpx
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class SlackService:
    """Send lead notifications to a Slack channel via Incoming Webhooks."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def notify_hot_lead(
        self,
        lead_data: dict[str, Any],
        score: int,
        status: str,
        recommended_action: str,
        dashboard_url: str,
    ) -> bool:
        """Send a rich notification for a hot lead.

        Returns True on success, False otherwise.
        """
        settings = self._settings
        if not settings.SLACK_WEBHOOK_URL:
            logger.warning(
                "SlackService: SLACK_WEBHOOK_URL is not set. "
                "Skipping hot-lead notification."
            )
            return False

        name: str    = lead_data.get("name", "Unknown")
        email: str   = lead_data.get("email", "")
        company: str = lead_data.get("company", "")
        budget: str  = str(lead_data.get("budget", "Not specified"))
        timeline: str = lead_data.get("timeline", "Not specified")

        score_emoji = self._score_emoji(score)
        status_emoji = self._status_emoji(status)

        blocks: list[dict[str, Any]] = [
            # ── Header ──────────────────────────────────────────────────
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{score_emoji} Hot Lead Alert — Action Required",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            # ── Lead identity ───────────────────────────────────────────
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Name:*\n{name}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Email:*\n{email}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Company:*\n{company if company else '_Not provided_'}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Score:*\n{score_emoji} *{score}/100*",
                    },
                ],
            },
            # ── Qualification details ────────────────────────────────────
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{status_emoji} {status.replace('_', ' ').title()}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Budget:*\n{budget}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Timeline:*\n{timeline}",
                    },
                ],
            },
            {"type": "divider"},
            # ── Recommended action ───────────────────────────────────────
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":bulb: *Recommended Action:*\n>{recommended_action}",
                },
            },
            # ── CTA button ───────────────────────────────────────────────
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Lead in Dashboard",
                            "emoji": True,
                        },
                        "style": "primary",
                        "url": dashboard_url,
                        "action_id": "view_lead_dashboard",
                    }
                ],
            },
            {"type": "divider"},
            # ── Footer ──────────────────────────────────────────────────
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":robot_face: AI Lead Qualification Agent",
                    }
                ],
            },
        ]

        payload: dict[str, Any] = {
            "text": f"{score_emoji} Hot Lead: {name} ({company}) — Score {score}/100",
            "blocks": blocks,
        }

        return await self._post_webhook(payload, context="hot_lead")

    async def notify_warm_lead(
        self,
        lead_data: dict[str, Any],
        score: int,
    ) -> bool:
        """Send a simpler notification for a warm lead.

        Returns True on success, False otherwise.
        """
        settings = self._settings
        if not settings.SLACK_WEBHOOK_URL:
            logger.warning(
                "SlackService: SLACK_WEBHOOK_URL is not set. "
                "Skipping warm-lead notification."
            )
            return False

        name: str    = lead_data.get("name", "Unknown")
        email: str   = lead_data.get("email", "")
        company: str = lead_data.get("company", "")
        score_emoji  = self._score_emoji(score)

        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{score_emoji} *Warm Lead Captured*\n"
                        f">*Name:* {name}  |  *Email:* {email}  |  "
                        f"*Company:* {company if company else '_N/A_'}  |  "
                        f"*Score:* {score}/100"
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":robot_face: AI Lead Qualification Agent",
                    }
                ],
            },
        ]

        payload: dict[str, Any] = {
            "text": f"{score_emoji} Warm Lead: {name} ({company}) — Score {score}/100",
            "blocks": blocks,
        }

        return await self._post_webhook(payload, context="warm_lead")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _post_webhook(
        self, payload: dict[str, Any], *, context: str
    ) -> bool:
        """POST *payload* to the configured Slack webhook URL."""
        if not self._settings.SLACK_WEBHOOK_URL:
            logger.warning("SlackService: SLACK_WEBHOOK_URL is not set.")
            return False
        webhook_url: str = self._settings.SLACK_WEBHOOK_URL

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload)
                # Slack returns plain-text "ok" on success
                if response.status_code == 200 and response.text.strip() == "ok":
                    logger.info(
                        "SlackService: %s notification sent successfully.", context
                    )
                    return True

                logger.error(
                    "SlackService: unexpected response for %s notification — "
                    "HTTP %s: %s",
                    context,
                    response.status_code,
                    response.text,
                )
                return False
        except httpx.RequestError as exc:
            logger.error(
                "SlackService: request error sending %s notification: %s",
                context,
                exc,
            )
            return False
        except Exception as exc:  # pragma: no cover
            logger.exception(
                "SlackService: unexpected error sending %s notification: %s",
                context,
                exc,
            )
            return False

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _score_emoji(score: int) -> str:
        if score >= 80:
            return ":fire:"
        if score >= 60:
            return ":large_yellow_circle:"
        return ":large_blue_circle:"

    @staticmethod
    def _status_emoji(status: str) -> str:
        status_lower = status.lower()
        emojis: dict[str, str] = {
            "hot":            ":fire:",
            "warm":           ":large_yellow_circle:",
            "cold":           ":snowflake:",
            "qualified":      ":white_check_mark:",
            "disqualified":   ":x:",
            "nurture":        ":seedling:",
            "follow_up":      ":telephone_receiver:",
        }
        for key, emoji in emojis.items():
            if key in status_lower:
                return emoji
        return ":bust_in_silhouette:"
