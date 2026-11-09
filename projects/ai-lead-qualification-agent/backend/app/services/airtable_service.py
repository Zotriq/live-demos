"""
Airtable integration service.

Creates a new record in a configured Airtable base/table using the
Airtable REST API v0.  The integration is opt-in: if AIRTABLE_ENABLED
is False, or if the required credentials are missing, every call returns
a "skipped" status.

Dependencies:
    pip install httpx
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Airtable REST API base URL
_AIRTABLE_API_BASE = "https://api.airtable.com/v0"


class AirtableService:
    """Sync a lead record to an Airtable table."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new Airtable record from *lead_data*.

        Returns a dict with at minimum:
            {
                "status":      "success" | "skipped" | "error",
                "message":     str,
                "external_id": str | None,   # Airtable record ID, e.g. "recXXXXXXXXXXXXXX"
                "sync_status": "success" | "skipped" | "error",
            }
        """
        settings = self._settings

        if not settings.AIRTABLE_ENABLED:
            logger.warning(
                "AirtableService: integration is disabled "
                "(AIRTABLE_ENABLED=False). Skipping sync."
            )
            return self._skipped("Airtable integration is disabled.")

        if not settings.AIRTABLE_API_KEY:
            logger.warning(
                "AirtableService: AIRTABLE_API_KEY is not set. Skipping sync."
            )
            return self._skipped("AIRTABLE_API_KEY is not configured.")

        if not settings.AIRTABLE_BASE_ID:
            logger.warning(
                "AirtableService: AIRTABLE_BASE_ID is not set. Skipping sync."
            )
            return self._skipped("AIRTABLE_BASE_ID is not configured.")

        try:
            return await self._create_record(lead_data)
        except Exception as exc:
            logger.exception("AirtableService: unexpected error during sync: %s", exc)
            return self._error(str(exc))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _create_record(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        settings = self._settings

        url = (
            f"{_AIRTABLE_API_BASE}"
            f"/{settings.AIRTABLE_BASE_ID}"
            f"/{settings.AIRTABLE_TABLE_NAME}"
        )
        headers = {
            "Authorization": f"Bearer {settings.AIRTABLE_API_KEY}",
            "Content-Type": "application/json",
        }
        fields = self._build_fields(lead_data)
        payload = {"fields": fields}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                body = exc.response.text
                logger.error(
                    "AirtableService: HTTP %s error creating record: %s",
                    exc.response.status_code,
                    body,
                )
                return self._error(
                    f"Airtable API returned HTTP {exc.response.status_code}: {body}"
                )
            except httpx.RequestError as exc:
                logger.error("AirtableService: request error: %s", exc)
                return self._error(f"Airtable request error: {exc}")

        data = response.json()
        record_id: str = data.get("id", "")
        logger.info(
            "AirtableService: created record '%s' in base '%s', table '%s'.",
            record_id,
            settings.AIRTABLE_BASE_ID,
            settings.AIRTABLE_TABLE_NAME,
        )
        return {
            "status": "success",
            "sync_status": "success",
            "message": f"Lead created in Airtable with record ID '{record_id}'.",
            "external_id": record_id,
        }

    @staticmethod
    def _build_fields(lead_data: dict[str, Any]) -> dict[str, Any]:
        """Convert *lead_data* to an Airtable fields dict."""
        fields: dict[str, Any] = {}

        field_map: list[tuple[str, str]] = [
            ("Lead ID",           "id"),
            ("Name",              "name"),
            ("Email",             "email"),
            ("Company",           "company"),
            ("Job Title",         "job_title"),
            ("Phone",             "phone"),
            ("Budget",            "budget"),
            ("Timeline",          "timeline"),
            ("Use Case",          "use_case"),
            ("Score",             "score"),
            ("Status",            "status"),
            ("Recommended Action","recommended_action"),
        ]

        for airtable_key, data_key in field_map:
            value = lead_data.get(data_key)
            if value is not None:
                # Airtable numeric fields must be numbers, not strings
                if airtable_key == "Score" and value != "":
                    try:
                        fields[airtable_key] = int(value)
                    except (TypeError, ValueError):
                        fields[airtable_key] = str(value)
                else:
                    fields[airtable_key] = str(value) if value != "" else ""

        return fields

    # ------------------------------------------------------------------
    # Response factories
    # ------------------------------------------------------------------

    @staticmethod
    def _skipped(message: str) -> dict[str, Any]:
        return {
            "status": "skipped",
            "sync_status": "skipped",
            "message": message,
            "external_id": None,
        }

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {
            "status": "error",
            "sync_status": "error",
            "message": message,
            "external_id": None,
        }
