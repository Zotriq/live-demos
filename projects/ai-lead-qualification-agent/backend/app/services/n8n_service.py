"""
n8n webhook integration service.

Forwards a lead payload (including AI score, status, and analysis) to a
configured n8n webhook URL via HTTP POST.  The integration is opt-in:
if N8N_WEBHOOK_ENABLED is False or N8N_WEBHOOK_URL is not set, every
call returns a "skipped" status.

Dependencies:
    pip install httpx
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class N8NService:
    """Forward lead data to an n8n automation workflow via webhook."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_lead_webhook(
        self,
        lead_data: dict[str, Any],
        score: int,
        status: str,
        ai_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """POST the full lead payload to the configured n8n webhook URL.

        Returns a dict with at minimum:
            {
                "status":   "success" | "skipped" | "error",
                "message":  str,
            }
        """
        settings = self._settings

        if not settings.N8N_WEBHOOK_ENABLED:
            logger.warning(
                "N8NService: n8n integration is disabled "
                "(N8N_WEBHOOK_ENABLED=False). Skipping webhook."
            )
            return self._skipped("n8n webhook integration is disabled.")

        if not settings.N8N_WEBHOOK_URL:
            logger.warning(
                "N8NService: N8N_WEBHOOK_URL is not set. Skipping webhook."
            )
            return self._skipped("N8N_WEBHOOK_URL is not configured.")

        try:
            return await self._post_webhook(lead_data, score, status, ai_analysis)
        except Exception as exc:
            logger.exception("N8NService: unexpected error sending webhook: %s", exc)
            return self._error(str(exc))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _post_webhook(
        self,
        lead_data: dict[str, Any],
        score: int,
        status: str,
        ai_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._build_payload(lead_data, score, status, ai_analysis)
        if not self._settings.N8N_WEBHOOK_URL:
            return self._skip("N8N_WEBHOOK_URL is not set.")
        webhook_url: str = self._settings.N8N_WEBHOOK_URL

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            logger.error(
                "N8NService: HTTP %s error from n8n webhook: %s",
                exc.response.status_code,
                body,
            )
            return self._error(
                f"n8n webhook returned HTTP {exc.response.status_code}: {body}"
            )
        except httpx.RequestError as exc:
            logger.error("N8NService: request error sending to n8n webhook: %s", exc)
            return self._error(f"n8n webhook request error: {exc}")

        logger.info(
            "N8NService: lead webhook sent successfully to n8n "
            "(HTTP %s, lead_id='%s').",
            response.status_code,
            lead_data.get("id", lead_data.get("lead_id", "unknown")),
        )
        return {
            "status": "success",
            "message": f"Lead webhook sent to n8n (HTTP {response.status_code}).",
        }

    @staticmethod
    def _build_payload(
        lead_data: dict[str, Any],
        score: int,
        status: str,
        ai_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble the full webhook payload sent to n8n."""
        return {
            "event": "lead.qualified",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lead": {
                "id":                 lead_data.get("id", lead_data.get("lead_id")),
                "name":               lead_data.get("name"),
                "email":              lead_data.get("email"),
                "company":            lead_data.get("company"),
                "job_title":          lead_data.get("job_title"),
                "phone":              lead_data.get("phone"),
                "budget":             lead_data.get("budget"),
                "timeline":           lead_data.get("timeline"),
                "use_case":           lead_data.get("use_case"),
            },
            "qualification": {
                "score":              score,
                "status":             status,
                "recommended_action": lead_data.get("recommended_action"),
            },
            "ai_analysis":            ai_analysis,
        }

    # ------------------------------------------------------------------
    # Response factories
    # ------------------------------------------------------------------

    @staticmethod
    def _skipped(message: str) -> dict[str, Any]:
        return {"status": "skipped", "message": message}

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"status": "error", "message": message}
