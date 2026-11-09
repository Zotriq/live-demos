"""
Google Sheets integration service.

Appends a new lead row to a configured Google Spreadsheet using a
service-account credential.  The integration is opt-in: if
GOOGLE_SHEETS_ENABLED is False, or if the required credentials /
spreadsheet ID are missing, every call returns a "skipped" status and
the rest of the application continues normally.

Dependencies (only needed when the integration is enabled):
    pip install google-api-python-client google-auth
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Sync a lead record to a Google Spreadsheet row."""

    # The first row of the sheet is expected to contain these headers in order.
    COLUMN_ORDER: list[str] = [
        "lead_id",
        "name",
        "email",
        "company",
        "job_title",
        "phone",
        "budget",
        "timeline",
        "use_case",
        "score",
        "status",
        "recommended_action",
        "synced_at",
    ]

    def __init__(self) -> None:
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """Append *lead_data* as a new row in the configured spreadsheet.

        Returns a dict with at minimum:
            {
                "status":      "success" | "skipped" | "error",
                "message":     str,
                "external_id": str | None,   # spreadsheet row range, e.g. "Sheet1!A5"
                "sync_status": "success" | "skipped" | "error",
            }
        """
        settings = self._settings

        if not settings.GOOGLE_SHEETS_ENABLED:
            logger.warning(
                "GoogleSheetsService: integration is disabled "
                "(GOOGLE_SHEETS_ENABLED=False). Skipping sync."
            )
            return self._skipped("Google Sheets integration is disabled.")

        if not settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            logger.warning(
                "GoogleSheetsService: GOOGLE_SERVICE_ACCOUNT_JSON is not set. "
                "Skipping sync."
            )
            return self._skipped("GOOGLE_SERVICE_ACCOUNT_JSON is not configured.")

        if not settings.GOOGLE_SHEETS_SPREADSHEET_ID:
            logger.warning(
                "GoogleSheetsService: GOOGLE_SHEETS_SPREADSHEET_ID is not set. "
                "Skipping sync."
            )
            return self._skipped("GOOGLE_SHEETS_SPREADSHEET_ID is not configured.")

        try:
            return await self._append_row(lead_data)
        except Exception as exc:  # pragma: no cover
            logger.exception("GoogleSheetsService: unexpected error during sync: %s", exc)
            return self._error(str(exc))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _append_row(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """Build the Sheets client and append one row (runs in a thread pool)."""
        import asyncio

        # google-api-python-client is synchronous; run it in a thread pool
        # so we do not block the async event loop.
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._append_row_sync, lead_data)
        return result

    def _append_row_sync(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """Synchronous implementation (called from a thread-pool executor)."""
        try:
            from google.oauth2.service_account import Credentials  # type: ignore
            from googleapiclient.discovery import build  # type: ignore
            from googleapiclient.errors import HttpError  # type: ignore
        except ImportError as exc:
            return self._error(
                "google-api-python-client / google-auth packages are not installed. "
                f"Run: pip install google-api-python-client google-auth  ({exc})"
            )

        settings = self._settings

        # Parse service-account JSON (plain JSON string or base64-encoded).
        raw_json = settings.GOOGLE_SERVICE_ACCOUNT_JSON
        try:
            sa_info = json.loads(raw_json)  # type: ignore[arg-type]
        except (json.JSONDecodeError, TypeError):
            try:
                # Attempt base64 decode
                decoded = base64.b64decode(raw_json).decode("utf-8")  # type: ignore[arg-type]
                sa_info = json.loads(decoded)
            except Exception as exc:
                return self._error(
                    f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {exc}"
                )

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        try:
            creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
        except Exception as exc:
            return self._error(f"Failed to build service-account credentials: {exc}")

        try:
            service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        except Exception as exc:
            return self._error(f"Failed to build Google Sheets API client: {exc}")

        spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
        row_values = self._build_row(lead_data)

        body = {
            "values": [row_values],
        }

        try:
            response = (
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range="Sheet1",
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body=body,
                )
                .execute()
            )
        except HttpError as exc:
            return self._error(f"Google Sheets API HTTP error: {exc}")
        except Exception as exc:
            return self._error(f"Google Sheets API error: {exc}")

        updated_range: str = (
            response.get("updates", {}).get("updatedRange", "unknown")
        )
        logger.info(
            "GoogleSheetsService: appended row to range '%s' in spreadsheet '%s'.",
            updated_range,
            spreadsheet_id,
        )
        return {
            "status": "success",
            "sync_status": "success",
            "message": f"Lead appended to Google Sheets at range '{updated_range}'.",
            "external_id": updated_range,
        }

    def _build_row(self, lead_data: dict[str, Any]) -> list[str]:
        """Map *lead_data* keys to an ordered list of cell values."""
        now_iso = datetime.now(timezone.utc).isoformat()

        mapping: dict[str, Any] = {
            "lead_id": str(lead_data.get("id", lead_data.get("lead_id", ""))),
            "name": lead_data.get("name", ""),
            "email": lead_data.get("email", ""),
            "company": lead_data.get("company", ""),
            "job_title": lead_data.get("job_title", ""),
            "phone": lead_data.get("phone", ""),
            "budget": str(lead_data.get("budget", "")),
            "timeline": lead_data.get("timeline", ""),
            "use_case": lead_data.get("use_case", ""),
            "score": str(lead_data.get("score", "")),
            "status": lead_data.get("status", ""),
            "recommended_action": lead_data.get("recommended_action", ""),
            "synced_at": now_iso,
        }
        return [str(mapping.get(col, "")) for col in self.COLUMN_ORDER]

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
