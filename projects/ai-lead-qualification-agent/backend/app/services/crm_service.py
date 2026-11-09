"""
HubSpot CRM integration service.

Creates or updates a HubSpot contact using the HubSpot Contacts API v3.
The integration is opt-in: if HUBSPOT_ENABLED is False, or if
HUBSPOT_API_KEY is not set, every call returns a "skipped" status.

The service first attempts to find an existing contact by email.  If one
is found it is updated; otherwise a new contact is created.

Dependencies:
    pip install httpx
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_HUBSPOT_API_BASE = "https://api.hubapi.com"


class CRMService:
    """Sync a lead to HubSpot as a Contact."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """Create or update a HubSpot contact from *lead_data*.

        Returns a dict with at minimum:
            {
                "status":      "success" | "skipped" | "error",
                "message":     str,
                "external_id": str | None,   # HubSpot contact ID
                "sync_status": "success" | "skipped" | "error",
            }
        """
        settings = self._settings

        if not settings.HUBSPOT_ENABLED:
            logger.warning(
                "CRMService: HubSpot integration is disabled "
                "(HUBSPOT_ENABLED=False). Skipping sync."
            )
            return self._skipped("HubSpot integration is disabled.")

        if not settings.HUBSPOT_API_KEY:
            logger.warning(
                "CRMService: HUBSPOT_API_KEY is not set. Skipping sync."
            )
            return self._skipped("HUBSPOT_API_KEY is not configured.")

        try:
            return await self._upsert_contact(lead_data)
        except Exception as exc:
            logger.exception("CRMService: unexpected error during HubSpot sync: %s", exc)
            return self._error(str(exc))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.HUBSPOT_API_KEY}",
            "Content-Type": "application/json",
        }

    async def _upsert_contact(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """Try to update an existing contact; fall back to creating one."""
        email: str = lead_data.get("email", "")
        if not email:
            return self._error(
                "Cannot sync to HubSpot: 'email' field is missing from lead data."
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            existing_id = await self._find_contact_by_email(client, email)
            if existing_id:
                return await self._update_contact(client, existing_id, lead_data)
            return await self._create_contact(client, lead_data)

    async def _find_contact_by_email(
        self, client: httpx.AsyncClient, email: str
    ) -> str | None:
        """Return the HubSpot contact ID if a contact with *email* exists."""
        url = f"{_HUBSPOT_API_BASE}/crm/v3/objects/contacts/{quote(email, safe='')}"
        params = {"idProperty": "email", "properties": "email"}
        try:
            response = await client.get(
                url, params=params, headers=self._auth_headers()
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("id")
            if response.status_code == 404:
                return None
            # Any other status: log and treat as "not found" to allow create.
            logger.warning(
                "CRMService: unexpected status %s when searching for contact '%s'.",
                response.status_code,
                email,
            )
            return None
        except httpx.RequestError as exc:
            logger.warning(
                "CRMService: request error while searching for contact '%s': %s",
                email,
                exc,
            )
            return None

    async def _create_contact(
        self, client: httpx.AsyncClient, lead_data: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{_HUBSPOT_API_BASE}/crm/v3/objects/contacts"
        payload = {"properties": self._build_properties(lead_data)}

        try:
            response = await client.post(
                url, json=payload, headers=self._auth_headers()
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            logger.error(
                "CRMService: HTTP %s creating HubSpot contact: %s",
                exc.response.status_code,
                body,
            )
            return self._error(
                f"HubSpot API returned HTTP {exc.response.status_code}: {body}"
            )
        except httpx.RequestError as exc:
            logger.error("CRMService: request error creating HubSpot contact: %s", exc)
            return self._error(f"HubSpot request error: {exc}")

        contact_id: str = response.json().get("id", "")
        logger.info("CRMService: created HubSpot contact id='%s'.", contact_id)
        return {
            "status": "success",
            "sync_status": "success",
            "message": f"HubSpot contact created with ID '{contact_id}'.",
            "external_id": contact_id,
        }

    async def _update_contact(
        self, client: httpx.AsyncClient, contact_id: str, lead_data: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{_HUBSPOT_API_BASE}/crm/v3/objects/contacts/{contact_id}"
        payload = {"properties": self._build_properties(lead_data)}

        try:
            response = await client.patch(
                url, json=payload, headers=self._auth_headers()
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            logger.error(
                "CRMService: HTTP %s updating HubSpot contact '%s': %s",
                exc.response.status_code,
                contact_id,
                body,
            )
            return self._error(
                f"HubSpot API returned HTTP {exc.response.status_code}: {body}"
            )
        except httpx.RequestError as exc:
            logger.error(
                "CRMService: request error updating HubSpot contact '%s': %s",
                contact_id,
                exc,
            )
            return self._error(f"HubSpot request error: {exc}")

        logger.info("CRMService: updated HubSpot contact id='%s'.", contact_id)
        return {
            "status": "success",
            "sync_status": "success",
            "message": f"HubSpot contact updated (ID '{contact_id}').",
            "external_id": contact_id,
        }

    @staticmethod
    def _build_properties(lead_data: dict[str, Any]) -> dict[str, str]:
        """Map *lead_data* to HubSpot standard / custom contact properties."""
        props: dict[str, str] = {}

        # HubSpot standard properties
        standard_map: list[tuple[str, str]] = [
            ("email",       "email"),
            ("firstname",   "name"),          # full name → firstname (simple split below)
            ("company",     "company"),
            ("jobtitle",    "job_title"),
            ("phone",       "phone"),
        ]
        for hs_prop, data_key in standard_map:
            value = lead_data.get(data_key)
            if value is not None and str(value).strip():
                props[hs_prop] = str(value)

        # Split full name into firstname / lastname if possible
        full_name: str = str(lead_data.get("name", "")).strip()
        if full_name and " " in full_name:
            parts = full_name.split(" ", 1)
            props["firstname"] = parts[0]
            props["lastname"] = parts[1]
        elif full_name:
            props["firstname"] = full_name

        # Custom properties (must be created in HubSpot CRM settings first)
        custom_map: list[tuple[str, str]] = [
            ("lead_budget",             "budget"),
            ("lead_timeline",           "timeline"),
            ("lead_use_case",           "use_case"),
            ("lead_score",              "score"),
            ("lead_status",             "status"),
            ("lead_recommended_action", "recommended_action"),
        ]
        for hs_prop, data_key in custom_map:
            value = lead_data.get(data_key)
            if value is not None and str(value).strip():
                props[hs_prop] = str(value)

        return props

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
