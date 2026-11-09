"""
Webhooks API router.

Accepts inbound webhook payloads from external systems and funnels them
into the standard lead intake pipeline.

Three webhook flavours are supported:

- ``POST /api/webhooks/lead``  — generic JSON lead payload (same fields as
  the public intake form).
- ``POST /api/webhooks/n8n``   — n8n workflow webhook format.
- ``POST /api/webhooks/crm``   — common CRM webhook payload format
  (HubSpot, Salesforce, Pipedrive-style).

All endpoints validate ``WEBHOOK_SECRET`` if one is configured, then
normalise the payload and delegate to the shared intake logic (same
function used by ``POST /api/leads/intake``).
"""

from __future__ import annotations

import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.activity import LeadActivity
from app.models.lead import Lead
from app.utils.normalization import (
    normalize_budget,
    normalize_company_size,
    normalize_industry,
    normalize_timeline,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _verify_webhook_secret(provided_secret: str | None) -> None:
    """
    Raise HTTP 401 if a webhook secret is configured but the caller did
    not supply a matching ``X-Webhook-Secret`` header.

    When ``WEBHOOK_SECRET`` is not configured this check is skipped so the
    endpoint is open (suitable for development / internal environments).
    """
    settings = get_settings()
    configured_secret = settings.WEBHOOK_SECRET

    if not configured_secret:
        # No secret configured — accept all requests
        return

    if not provided_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required 'X-Webhook-Secret' header.",
        )

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(
        configured_secret.encode("utf-8"),
        provided_secret.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret.",
        )


async def _log_activity(
    db: AsyncSession,
    lead_id: uuid.UUID,
    activity_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist a LeadActivity row, swallowing errors so webhooks never crash."""
    try:
        activity = LeadActivity(
            lead_id=lead_id,
            activity_type=activity_type,
            message=message,
            metadata_json=metadata,
        )
        db.add(activity)
        await db.flush()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Webhook: failed to log activity '%s' for lead %s: %s",
            activity_type,
            lead_id,
            exc,
        )


async def _intake_from_dict(
    data: dict[str, Any],
    source_override: str,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Shared intake logic: persist a Lead from a normalised dict and queue
    background qualification.

    Parameters
    ----------
    data:
        Normalised lead fields (name, email, company, etc.).
    source_override:
        The ``source`` value to stamp on the lead (e.g. ``"n8n_webhook"``).
    db:
        Active AsyncSession (from ``Depends(get_db)``).
    background_tasks:
        FastAPI BackgroundTasks instance.
    raw_payload:
        The original, un-normalised request body for audit purposes.
    """
    # ---- Validate required fields ----------------------------------------
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload must include a valid 'email' field.",
        )

    name = data.get("name", "").strip() or email.split("@")[0]

    # ---- Normalise --------------------------------------------------------
    budget_str = str(data.get("budget", "")) if data.get("budget") else None
    budget_min, budget_max = normalize_budget(budget_str)
    timeline_norm = normalize_timeline(data.get("timeline"))
    industry_norm = normalize_industry(data.get("industry"))

    # ---- Persist ----------------------------------------------------------
    lead = Lead(
        name=name,
        email=email,
        phone=data.get("phone"),
        company=data.get("company"),
        company_size=data.get("company_size"),
        industry=industry_norm or data.get("industry"),
        job_title=data.get("job_title"),
        budget=budget_str,
        normalized_budget_min=budget_min,
        normalized_budget_max=budget_max,
        timeline=timeline_norm,
        source=source_override,
        message=data.get("message") or data.get("notes"),
        project_type=data.get("project_type"),
        country=data.get("country"),
        raw_payload=raw_payload,
        qualification_status="processing",
    )
    db.add(lead)
    await db.flush()  # populate lead.id

    await _log_activity(
        db,
        lead.id,
        "lead_created",
        f"Lead received via webhook '{source_override}' for {name} <{email}>.",
        {"source": source_override, "budget": budget_str, "timeline": timeline_norm},
    )

    await db.commit()

    # ---- Queue background qualification -----------------------------------
    # Import here to avoid circular imports
    from app.routes.leads import _run_qualification  # noqa: PLC0415

    lead_id = lead.id
    background_tasks.add_task(_run_qualification, lead_id)

    logger.info(
        "Webhook '%s': lead %s created for %s <%s> — qualification queued.",
        source_override,
        lead_id,
        name,
        email,
    )

    return {
        "lead_id": str(lead_id),
        "status": "processing",
        "source": source_override,
        "message": "Lead received via webhook. Qualification is running in the background.",
    }


# ---------------------------------------------------------------------------
# Generic lead webhook
# ---------------------------------------------------------------------------


@router.post(
    "/lead",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generic webhook endpoint for lead intake",
    response_description="Lead accepted and qualification queued.",
)
async def webhook_lead(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Accept a raw JSON lead payload from any external system.

    The payload must include at minimum an ``email`` field.  All other
    fields follow the same naming convention as ``POST /api/leads/intake``.

    If ``WEBHOOK_SECRET`` is configured in the environment, the caller must
    supply a matching ``X-Webhook-Secret`` header.
    """
    _verify_webhook_secret(x_webhook_secret)

    try:
        body: dict[str, Any] = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {exc}",
        ) from exc

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload must be a JSON object.",
        )

    # Allow callers to override the source label; default to "generic_webhook"
    source = str(body.get("source", "generic_webhook"))

    return await _intake_from_dict(
        data=body,
        source_override=source,
        db=db,
        background_tasks=background_tasks,
        raw_payload=body,
    )


# ---------------------------------------------------------------------------
# n8n webhook
# ---------------------------------------------------------------------------

# Mapping from n8n workflow field names to normalised lead field names.
# Keys are possible n8n field names; values are the canonical lead field names.
_N8N_FIELD_MAP: dict[str, str] = {
    # Contact
    "full_name": "name",
    "fullName": "name",
    "contact_name": "name",
    "contactName": "name",
    "email_address": "email",
    "emailAddress": "email",
    "phone_number": "phone",
    "phoneNumber": "phone",
    # Company
    "company_name": "company",
    "companyName": "company",
    "organization": "company",
    "organisation": "company",
    "company_size": "company_size",
    "companySize": "company_size",
    "employees": "company_size",
    "num_employees": "company_size",
    # Role
    "job_title": "job_title",
    "jobTitle": "job_title",
    "title": "job_title",
    "position": "job_title",
    "role": "job_title",
    # Budget / timeline
    "budget_range": "budget",
    "budgetRange": "budget",
    "project_budget": "budget",
    "projectBudget": "budget",
    "start_date": "timeline",
    "startDate": "timeline",
    "project_timeline": "timeline",
    "projectTimeline": "timeline",
    # Other
    "project_description": "message",
    "projectDescription": "message",
    "use_case": "message",
    "useCase": "message",
    "notes": "message",
    "project_type": "project_type",
    "projectType": "project_type",
    "country_code": "country",
    "countryCode": "country",
    "lead_source": "source",
    "leadSource": "source",
}


def _map_n8n_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalise an n8n webhook payload to the canonical lead field dict.

    Handles both snake_case and camelCase field names.  Nested ``lead``
    or ``data`` wrappers are flattened first.
    """
    # Unwrap common n8n envelope shapes
    if "lead" in raw and isinstance(raw["lead"], dict):
        raw = {**raw["lead"], **{k: v for k, v in raw.items() if k != "lead"}}
    elif "data" in raw and isinstance(raw["data"], dict):
        raw = {**raw["data"], **{k: v for k, v in raw.items() if k != "data"}}
    elif "body" in raw and isinstance(raw["body"], dict):
        raw = {**raw["body"], **{k: v for k, v in raw.items() if k != "body"}}

    # Flatten qualification sub-object if present
    qual = raw.get("qualification", {})
    if isinstance(qual, dict):
        raw = {**raw, **qual}

    mapped: dict[str, Any] = {}

    for raw_key, raw_val in raw.items():
        # Direct canonical match
        if raw_key in (
            "name", "email", "phone", "company", "company_size", "industry",
            "job_title", "budget", "timeline", "source", "message",
            "project_type", "country",
        ):
            mapped[raw_key] = raw_val
        # Aliased match
        elif raw_key in _N8N_FIELD_MAP:
            canonical = _N8N_FIELD_MAP[raw_key]
            # Don't overwrite if already set by a canonical key
            if canonical not in mapped:
                mapped[canonical] = raw_val

    return mapped


@router.post(
    "/n8n",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive a lead from an n8n automation workflow",
    response_description="Lead accepted and qualification queued.",
)
async def webhook_n8n(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Accept a lead payload posted from an n8n workflow.

    The payload is mapped from n8n field names (camelCase or snake_case)
    to the canonical lead schema and then processed identically to a
    normal intake form submission.

    If ``WEBHOOK_SECRET`` is configured in the environment, the caller must
    supply a matching ``X-Webhook-Secret`` header.
    """
    _verify_webhook_secret(x_webhook_secret)

    try:
        body: dict[str, Any] = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {exc}",
        ) from exc

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="n8n payload must be a JSON object.",
        )

    mapped = _map_n8n_payload(body)

    return await _intake_from_dict(
        data=mapped,
        source_override="n8n_webhook",
        db=db,
        background_tasks=background_tasks,
        raw_payload=body,
    )


# ---------------------------------------------------------------------------
# CRM webhook
# ---------------------------------------------------------------------------

# Mapping for common CRM systems (HubSpot, Salesforce, Pipedrive).
_CRM_FIELD_MAP: dict[str, str] = {
    # HubSpot contact properties
    "firstname": "name",
    "lastname": "_last_name",          # combined below
    "email": "email",
    "phone": "phone",
    "mobilephone": "phone",
    "company": "company",
    "jobtitle": "job_title",
    "industry": "industry",
    "numberofemployees": "company_size",
    "hs_lead_status": "qualification_status",
    "country": "country",
    "message": "message",
    "description": "message",
    "lead_source": "source",
    "hs_analytics_source": "source",
    # Salesforce
    "FirstName": "name",
    "LastName": "_last_name",
    "Email": "email",
    "Phone": "phone",
    "Company": "company",
    "Title": "job_title",
    "Industry": "industry",
    "NumberOfEmployees": "company_size",
    "Country": "country",
    "Description": "message",
    "LeadSource": "source",
    "AnnualRevenue": "budget",
    # Pipedrive
    "person_name": "name",
    "org_name": "company",
    "email_address": "email",
    "phone_number": "phone",
    "job_title": "job_title",
    # Generic
    "full_name": "name",
    "contact_email": "email",
    "contact_phone": "phone",
    "company_name": "company",
    "budget_amount": "budget",
    "project_budget": "budget",
    "timeline": "timeline",
    "project_timeline": "timeline",
    "notes": "message",
    "project_description": "message",
}


def _map_crm_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalise a CRM webhook payload to the canonical lead field dict.

    Handles HubSpot, Salesforce, and Pipedrive payload shapes.  Nested
    ``properties``, ``contact``, ``lead``, or ``person`` wrappers are
    flattened first.
    """
    # Unwrap common CRM envelope shapes
    for wrapper_key in ("properties", "contact", "lead", "person", "record", "data"):
        if wrapper_key in raw and isinstance(raw[wrapper_key], dict):
            raw = {**raw[wrapper_key], **{k: v for k, v in raw.items() if k != wrapper_key}}
            break

    # Some CRM systems nest field values under a "value" key, e.g.:
    #   {"email": {"value": "foo@bar.com"}}
    def _extract(val: Any) -> Any:
        if isinstance(val, dict) and "value" in val:
            return val["value"]
        return val

    mapped: dict[str, Any] = {}
    last_name: str = ""

    for raw_key, raw_val in raw.items():
        extracted = _extract(raw_val)

        # Direct canonical match
        if raw_key in (
            "name", "email", "phone", "company", "company_size", "industry",
            "job_title", "budget", "timeline", "source", "message",
            "project_type", "country",
        ):
            mapped[raw_key] = extracted
            continue

        # Aliased match
        crm_key = _CRM_FIELD_MAP.get(raw_key)
        if crm_key == "_last_name":
            last_name = str(extracted or "")
        elif crm_key and crm_key not in mapped:
            mapped[crm_key] = extracted

    # Combine first + last name when coming from HubSpot / Salesforce
    if "name" in mapped and last_name:
        mapped["name"] = f"{mapped['name']} {last_name}".strip()
    elif last_name and "name" not in mapped:
        mapped["name"] = last_name

    # Some CRM systems send numeric employee count — keep as string for normaliser
    if "company_size" in mapped and mapped["company_size"] is not None:
        mapped["company_size"] = str(mapped["company_size"])

    return mapped


@router.post(
    "/crm",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive a lead from a CRM system webhook",
    response_description="Lead accepted and qualification queued.",
)
async def webhook_crm(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    x_crm_source: str | None = Header(
        default=None,
        alias="X-CRM-Source",
        description="Optional header identifying the originating CRM (e.g. 'hubspot', 'salesforce').",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Accept a lead payload posted from a CRM system (HubSpot, Salesforce,
    Pipedrive, or any system with a similar JSON structure).

    The payload is mapped to the canonical lead schema using a broad field
    mapping that covers the most common CRM property names.

    The ``X-CRM-Source`` header is optional — if supplied it is used as the
    ``source`` label on the lead record (e.g. ``"hubspot_webhook"``).  If
    omitted, the source defaults to ``"crm_webhook"``.

    If ``WEBHOOK_SECRET`` is configured in the environment, the caller must
    supply a matching ``X-Webhook-Secret`` header.
    """
    _verify_webhook_secret(x_webhook_secret)

    try:
        body: Any = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {exc}",
        ) from exc

    # Some CRM systems POST an array of event objects; take the first element.
    if isinstance(body, list):
        if not body:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="CRM webhook payload array is empty.",
            )
        body = body[0]

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CRM webhook payload must be a JSON object or a non-empty JSON array.",
        )

    # Determine source label
    source_label = "crm_webhook"
    if x_crm_source:
        safe_source = x_crm_source.lower().strip().replace(" ", "_")
        source_label = f"{safe_source}_webhook" if not safe_source.endswith("_webhook") else safe_source

    mapped = _map_crm_payload(body)

    # Allow source override from within the payload itself
    if "source" not in mapped:
        mapped["source"] = source_label

    return await _intake_from_dict(
        data=mapped,
        source_override=mapped.get("source", source_label),
        db=db,
        background_tasks=background_tasks,
        raw_payload=body,
    )
