"""
Leads API router.

Handles lead intake, listing, retrieval, update, deletion, and manual
re-qualification / re-sync / re-notification triggers.

All write operations that kick off heavy work (AI scoring, integrations,
notifications) use FastAPI BackgroundTasks so the HTTP response is returned
immediately while processing continues asynchronously.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models.activity import LeadActivity
from app.models.follow_up_email import FollowUpEmail
from app.models.integration_sync import IntegrationSync
from app.models.lead import Lead
from app.schemas.lead import (
    LeadIntakeRequest,
    LeadListResponse,
    LeadResponse,
    LeadUpdateRequest,
)
from app.utils.normalization import (
    normalize_budget,
    normalize_company_size,
    normalize_industry,
    normalize_timeline,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leads", tags=["Leads"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _lead_to_dict(lead: Lead) -> dict[str, Any]:
    """Serialise a Lead ORM object to a plain dict for service calls."""
    return {
        "id": str(lead.id),
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "company": lead.company,
        "company_size": lead.company_size,
        "industry": lead.industry,
        "job_title": lead.job_title,
        "budget": lead.budget,
        "timeline": lead.timeline,
        "source": lead.source,
        "message": lead.message,
        "project_type": lead.project_type,
        "country": lead.country,
        "score": lead.score,
        "status": lead.qualification_status,
        "recommended_action": lead.recommended_next_action,
    }


def _build_lead_response(lead: Lead) -> dict[str, Any]:
    """Build a full lead response dict including related records."""
    data = _lead_to_dict(lead)
    data["ai_analysis"] = lead.ai_analysis_json
    data["created_at"] = lead.created_at.isoformat() if lead.created_at else None
    data["updated_at"] = lead.updated_at.isoformat() if lead.updated_at else None

    # Include related records if already loaded
    try:
        data["follow_up_emails"] = [
            {
                "id": str(e.id),
                "subject": e.subject,
                "body": e.body,
                "status": e.status,
                "ai_generated": e.ai_generated,
                "approved_by": e.approved_by,
                "approved_at": e.approved_at.isoformat() if e.approved_at else None,
                "sent_at": e.sent_at.isoformat() if e.sent_at else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in (lead.follow_up_emails or [])
        ]
    except Exception:  # noqa: BLE001
        data["follow_up_emails"] = []

    try:
        data["activities"] = [
            {
                "id": str(a.id),
                "activity_type": a.activity_type,
                "message": a.message,
                "metadata": a.metadata_json,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in (lead.activities or [])
        ]
    except Exception:  # noqa: BLE001
        data["activities"] = []

    try:
        data["integration_syncs"] = [
            {
                "id": str(s.id),
                "integration_name": s.integration_name,
                "sync_status": s.sync_status,
                "external_id": s.external_id,
                "error_message": s.error_message,
                "synced_at": s.synced_at.isoformat() if s.synced_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in (lead.integration_syncs or [])
        ]
    except Exception:  # noqa: BLE001
        data["integration_syncs"] = []

    return data


async def _log_activity(
    db: AsyncSession,
    lead_id: uuid.UUID,
    activity_type: str,
    message: str,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Persist a LeadActivity row without raising on failure."""
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
        logger.error("Failed to log activity '%s' for lead %s: %s", activity_type, lead_id, exc)


async def _record_integration_sync(
    db: AsyncSession,
    lead_id: uuid.UUID,
    integration_name: str,
    result: dict[str, Any],
) -> None:
    """Persist an IntegrationSync row from a service result dict."""
    try:
        sync_status = result.get("sync_status") or result.get("status", "error")
        external_id = result.get("external_id")
        error_msg = result.get("message") if sync_status == "error" else None
        synced_at = _utcnow() if sync_status == "success" else None

        sync = IntegrationSync(
            lead_id=lead_id,
            integration_name=integration_name,
            sync_status=sync_status,
            external_id=external_id,
            error_message=error_msg,
            synced_at=synced_at,
        )
        db.add(sync)
        await db.flush()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to record integration sync '%s' for lead %s: %s",
            integration_name,
            lead_id,
            exc,
        )


# ---------------------------------------------------------------------------
# Background qualification task
# ---------------------------------------------------------------------------


async def _run_qualification(lead_id: uuid.UUID) -> None:
    """
    Full async qualification pipeline for a lead.

    Steps
    -----
    1. Load lead from DB.
    2. Run rule-based scoring engine.
    3. Run AI analysis (blends 60 % AI + 40 % rules internally).
    4. Persist combined score, status, ai_analysis_json, recommended_next_action.
    5. Create FollowUpEmail record with AI-generated email draft.
    6. Log all activities.
    7. Sync to Google Sheets, Airtable, HubSpot if enabled.
    8. Send to n8n webhook if enabled.
    9. Send Slack notification for hot/warm leads.

    All sub-steps are individually wrapped in try/except to ensure one
    failure never cascades to abort the entire pipeline.
    """
    from app.database import _get_session_factory  # noqa: PLC0415

    factory = _get_session_factory()
    async with factory() as db:
        try:
            # ----------------------------------------------------------------
            # 1. Load the lead
            # ----------------------------------------------------------------
            result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()
            if lead is None:
                logger.error("Qualification task: lead %s not found.", lead_id)
                return

            lead_data = _lead_to_dict(lead)

            # ----------------------------------------------------------------
            # 2. Rule-based scoring
            # ----------------------------------------------------------------
            rule_score: int = 0
            rule_status: str = "unqualified"
            rule_breakdown: dict[str, Any] = {}

            try:
                from app.services.scoring_engine import ScoringEngine  # noqa: PLC0415

                engine = ScoringEngine()
                rule_result = engine.score_lead(lead_data)
                rule_score = rule_result.get("score", 0)
                rule_status = rule_result.get("qualification_status", "unqualified")
                rule_breakdown = rule_result.get("breakdown", {})
                logger.info(
                    "Qualification: rule score=%s status=%s for lead %s",
                    rule_score,
                    rule_status,
                    lead_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Scoring engine failed for lead %s: %s", lead_id, exc)

            # ----------------------------------------------------------------
            # 3. AI analysis (includes internal score blending)
            # ----------------------------------------------------------------
            ai_analysis: dict[str, Any] = {}
            final_score: int = rule_score
            final_status: str = rule_status
            recommended_action: str = "Review lead manually."
            email_subject: str = "Following up on your inquiry"
            email_body: str = (
                f"Hi {lead.name or 'there'},\n\n"
                "Thank you for reaching out. We will be in touch shortly.\n\n"
                "Best regards,\nThe Sales Team"
            )

            try:
                from app.services.ai_lead_analyzer import AILeadAnalyzer  # noqa: PLC0415

                settings = get_settings()
                analyzer = AILeadAnalyzer(
                    api_key=settings.OPENAI_API_KEY or None,
                    model=settings.OPENAI_MODEL,
                )
                ai_analysis = await analyzer.analyze_lead(lead_data, rule_score=rule_score)
                final_score = ai_analysis.get("final_score", rule_score)
                final_status = ai_analysis.get("qualification_status", rule_status)
                recommended_action = ai_analysis.get(
                    "recommended_next_action", recommended_action
                )
                follow_up_email = ai_analysis.get("follow_up_email", {})
                email_subject = follow_up_email.get("subject", email_subject)
                email_body = follow_up_email.get("body", email_body)
                # Merge rule breakdown into analysis for traceability
                ai_analysis["rule_breakdown"] = rule_breakdown
                logger.info(
                    "Qualification: final score=%s status=%s for lead %s",
                    final_score,
                    final_status,
                    lead_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("AI analysis failed for lead %s: %s", lead_id, exc)

            # ----------------------------------------------------------------
            # 4. Persist score + status + analysis + recommended action
            # ----------------------------------------------------------------
            try:
                lead.score = final_score
                lead.qualification_status = final_status
                lead.ai_analysis_json = ai_analysis
                lead.recommended_next_action = recommended_action
                lead.updated_at = _utcnow()
                await db.flush()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to persist qualification for lead %s: %s", lead_id, exc)
                await db.rollback()
                return

            # ----------------------------------------------------------------
            # 5. Create FollowUpEmail record
            # ----------------------------------------------------------------
            try:
                follow_up = FollowUpEmail(
                    lead_id=lead.id,
                    subject=email_subject,
                    body=email_body,
                    status="draft_generated",
                    ai_generated=True,
                )
                db.add(follow_up)
                await db.flush()
                logger.info("FollowUpEmail created for lead %s.", lead_id)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to create FollowUpEmail for lead %s: %s", lead_id, exc)

            # ----------------------------------------------------------------
            # 6. Log activities
            # ----------------------------------------------------------------
            await _log_activity(
                db,
                lead.id,
                "ai_analysis_done",
                f"AI qualification completed. Score={final_score}, Status={final_status}.",
                {
                    "score": final_score,
                    "status": final_status,
                    "rule_score": rule_score,
                    "ai_available": ai_analysis.get("ai_available", False),
                },
            )
            await _log_activity(
                db,
                lead.id,
                "email_drafted",
                f"Follow-up email draft generated: '{email_subject}'.",
                {"subject": email_subject},
            )

            # Commit all DB changes before firing off external integrations
            try:
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to commit qualification changes for lead %s: %s", lead_id, exc
                )
                await db.rollback()
                return

            # ----------------------------------------------------------------
            # 7. Sync to external integrations
            # ----------------------------------------------------------------
            settings = get_settings()
            sync_payload = {
                **lead_data,
                "score": final_score,
                "status": final_status,
                "recommended_action": recommended_action,
            }

            # Google Sheets
            if settings.GOOGLE_SHEETS_ENABLED:
                try:
                    from app.services.google_sheets_service import GoogleSheetsService  # noqa: PLC0415

                    sheets_result = await GoogleSheetsService().sync_lead(sync_payload)
                    await _record_integration_sync(
                        db, lead.id, "google_sheets", sheets_result
                    )
                    await _log_activity(
                        db,
                        lead.id,
                        "crm_synced",
                        f"Google Sheets sync: {sheets_result.get('status', 'unknown')}.",
                        sheets_result,
                    )
                    await db.commit()
                    logger.info("Google Sheets sync complete for lead %s.", lead_id)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Google Sheets sync failed for lead %s: %s", lead_id, exc)

            # Airtable
            if settings.AIRTABLE_ENABLED:
                try:
                    from app.services.airtable_service import AirtableService  # noqa: PLC0415

                    airtable_result = await AirtableService().sync_lead(sync_payload)
                    await _record_integration_sync(
                        db, lead.id, "airtable", airtable_result
                    )
                    await _log_activity(
                        db,
                        lead.id,
                        "crm_synced",
                        f"Airtable sync: {airtable_result.get('status', 'unknown')}.",
                        airtable_result,
                    )
                    await db.commit()
                    logger.info("Airtable sync complete for lead %s.", lead_id)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Airtable sync failed for lead %s: %s", lead_id, exc)

            # HubSpot
            if settings.HUBSPOT_ENABLED:
                try:
                    from app.services.crm_service import CRMService  # noqa: PLC0415

                    hubspot_result = await CRMService().sync_lead(sync_payload)
                    await _record_integration_sync(
                        db, lead.id, "hubspot", hubspot_result
                    )
                    await _log_activity(
                        db,
                        lead.id,
                        "crm_synced",
                        f"HubSpot sync: {hubspot_result.get('status', 'unknown')}.",
                        hubspot_result,
                    )
                    await db.commit()
                    logger.info("HubSpot sync complete for lead %s.", lead_id)
                except Exception as exc:  # noqa: BLE001
                    logger.error("HubSpot sync failed for lead %s: %s", lead_id, exc)

            # ----------------------------------------------------------------
            # 8. n8n webhook
            # ----------------------------------------------------------------
            if settings.N8N_WEBHOOK_ENABLED:
                try:
                    from app.services.n8n_service import N8NService  # noqa: PLC0415

                    n8n_result = await N8NService().send_lead_webhook(
                        lead_data=sync_payload,
                        score=final_score,
                        status=final_status,
                        ai_analysis=ai_analysis,
                    )
                    await _log_activity(
                        db,
                        lead.id,
                        "n8n_webhook_sent",
                        f"n8n webhook: {n8n_result.get('status', 'unknown')}.",
                        n8n_result,
                    )
                    await db.commit()
                    logger.info("n8n webhook sent for lead %s.", lead_id)
                except Exception as exc:  # noqa: BLE001
                    logger.error("n8n webhook failed for lead %s: %s", lead_id, exc)

            # ----------------------------------------------------------------
            # 9. Slack notification (hot and warm leads)
            # ----------------------------------------------------------------
            if settings.SLACK_WEBHOOK_URL:
                try:
                    from app.services.slack_service import SlackService  # noqa: PLC0415

                    slack = SlackService()
                    dashboard_url = (
                        f"{settings.APP_BASE_URL}/leads/{lead_id}"
                    )

                    if final_status == "hot":
                        sent = await slack.notify_hot_lead(
                            lead_data=sync_payload,
                            score=final_score,
                            status=final_status,
                            recommended_action=recommended_action,
                            dashboard_url=dashboard_url,
                        )
                    elif final_status == "warm":
                        sent = await slack.notify_warm_lead(
                            lead_data=sync_payload,
                            score=final_score,
                        )
                    else:
                        sent = False

                    if sent:
                        await _log_activity(
                            db,
                            lead.id,
                            "slack_notified",
                            f"Slack notification sent for {final_status} lead.",
                            {"score": final_score, "status": final_status},
                        )
                        await db.commit()
                        logger.info("Slack notification sent for lead %s.", lead_id)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Slack notification failed for lead %s: %s", lead_id, exc)

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Unhandled error in qualification pipeline for lead %s: %s", lead_id, exc
            )
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/intake",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new lead for qualification",
    response_description="Lead accepted and qualification queued.",
)
async def intake_lead(
    payload: LeadIntakeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Accept a new lead form submission, persist it to the database, and
    trigger background qualification (scoring, AI analysis, integrations,
    notifications).

    Returns the ``lead_id`` and a ``status`` of ``"processing"`` immediately
    while qualification runs in the background.
    """
    # ---- Normalise fields ------------------------------------------------
    budget_min, budget_max = normalize_budget(payload.budget)
    timeline_norm = normalize_timeline(payload.timeline)
    company_size_norm = normalize_company_size(payload.company_size)
    industry_norm = normalize_industry(payload.industry)

    # ---- Persist lead record ---------------------------------------------
    lead = Lead(
        name=payload.name,
        email=str(payload.email),
        phone=payload.phone,
        company=payload.company,
        company_size=payload.company_size,
        industry=industry_norm or payload.industry,
        job_title=payload.job_title,
        budget=payload.budget,
        normalized_budget_min=budget_min,
        normalized_budget_max=budget_max,
        timeline=timeline_norm,
        source=payload.source,
        message=payload.message,
        project_type=payload.project_type,
        country=payload.country,
        raw_payload=payload.model_dump(),
        qualification_status="processing",
    )
    db.add(lead)

    # Log lead_created activity before flush so we can use lead.id
    await db.flush()  # populates lead.id

    await _log_activity(
        db,
        lead.id,
        "lead_created",
        f"Lead submitted by {payload.name} <{payload.email}> via {payload.source}.",
        {"source": payload.source, "budget": payload.budget, "timeline": timeline_norm},
    )

    await db.commit()

    # ---- Trigger background qualification --------------------------------
    lead_id = lead.id
    background_tasks.add_task(_run_qualification, lead_id)

    logger.info("Lead %s created and qualification queued.", lead_id)
    return {
        "lead_id": str(lead_id),
        "status": "processing",
        "message": "Lead received. Qualification is running in the background.",
    }


@router.get(
    "/",
    summary="List leads with pagination and filters",
)
async def list_leads(
    page: int = Query(default=1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(default=20, ge=1, le=200, description="Records per page."),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by qualification_status (hot, warm, cold, unqualified, processing).",
    ),
    source: Optional[str] = Query(default=None, description="Filter by lead source."),
    search: Optional[str] = Query(
        default=None,
        description="Full-text search across name, email, and company.",
    ),
    sort_by: str = Query(
        default="created_at",
        description="Sort field: 'score' or 'created_at'.",
    ),
    sort_order: str = Query(
        default="desc",
        description="Sort direction: 'asc' or 'desc'.",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return a paginated, filterable list of leads.

    Supported filters: ``status``, ``source``, free-text ``search``
    (matches name, email, company).  Results can be sorted by ``score``
    or ``created_at``.
    """
    stmt = select(Lead)

    # ---- Filters ---------------------------------------------------------
    if status_filter:
        stmt = stmt.where(Lead.qualification_status == status_filter)

    if source:
        stmt = stmt.where(Lead.source == source)

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Lead.name.ilike(pattern),
                Lead.email.ilike(pattern),
                Lead.company.ilike(pattern),
            )
        )

    # ---- Sorting ---------------------------------------------------------
    sort_col = Lead.score if sort_by == "score" else Lead.created_at
    if sort_order.lower() == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())

    # ---- Total count (re-uses same filters, no pagination) ---------------
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    # ---- Pagination ------------------------------------------------------
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    leads = result.scalars().all()

    return {
        "leads": [_build_lead_response(lead) for lead in leads],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.get(
    "/{lead_id}",
    summary="Get a single lead with related records",
)
async def get_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return a single lead record together with its ``follow_up_emails``,
    ``activities``, and ``integration_syncs`` relationships.
    """
    stmt = (
        select(Lead)
        .where(Lead.id == lead_id)
        .options(
            selectinload(Lead.follow_up_emails),
            selectinload(Lead.activities),
            selectinload(Lead.integration_syncs),
        )
    )
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found.",
        )

    return _build_lead_response(lead)


@router.put(
    "/{lead_id}",
    summary="Update lead fields",
)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Partially update a lead record.  Only fields present in the request
    body are modified.  At least one field must be supplied.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found.",
        )

    updated_fields: list[str] = []
    update_data = payload.model_dump(exclude_none=True)

    # Field mapping: schema key -> model attribute
    field_map: dict[str, str] = {
        "name": "name",
        "email": "email",
        "phone": "phone",
        "company": "company",
        "company_size": "company_size",
        "industry": "industry",
        "job_title": "job_title",
        "budget": "budget",
        "timeline": "timeline",
        "source": "source",
        "message": "message",
        "project_type": "project_type",
        "country": "country",
        "score": "score",
        "qualification_status": "qualification_status",
    }

    for schema_key, model_attr in field_map.items():
        if schema_key in update_data:
            value = update_data[schema_key]
            # Convert email to string if it's an EmailStr
            if schema_key == "email":
                value = str(value)
            setattr(lead, model_attr, value)
            updated_fields.append(schema_key)

    # Re-normalise budget / timeline if they were updated
    if "budget" in update_data:
        bmin, bmax = normalize_budget(lead.budget)
        lead.normalized_budget_min = bmin
        lead.normalized_budget_max = bmax

    if "timeline" in update_data:
        lead.timeline = normalize_timeline(lead.timeline)

    lead.updated_at = _utcnow()

    await _log_activity(
        db,
        lead.id,
        "status_changed",
        f"Lead fields updated: {', '.join(updated_fields)}.",
        {"updated_fields": updated_fields},
    )

    await db.commit()
    await db.refresh(lead)

    logger.info("Lead %s updated. Fields changed: %s", lead_id, updated_fields)
    return _build_lead_response(lead)


@router.delete(
    "/{lead_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a lead",
)
async def delete_lead(
    lead_id: uuid.UUID,
    hard: bool = Query(
        default=False,
        description="If true, permanently delete the record. Default is soft-delete (sets status to 'deleted').",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Delete a lead.

    By default performs a soft-delete by setting ``qualification_status``
    to ``"deleted"``.  Pass ``hard=true`` to permanently remove the record
    and all cascade-related rows (follow_up_emails, activities, integration_syncs).
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found.",
        )

    if hard:
        await db.delete(lead)
        await db.commit()
        logger.info("Lead %s hard-deleted.", lead_id)
        return {
            "lead_id": str(lead_id),
            "deleted": True,
            "type": "hard",
            "message": "Lead permanently deleted.",
        }
    else:
        lead.qualification_status = "deleted"
        lead.updated_at = _utcnow()
        await _log_activity(
            db,
            lead.id,
            "status_changed",
            "Lead soft-deleted (status set to 'deleted').",
        )
        await db.commit()
        logger.info("Lead %s soft-deleted.", lead_id)
        return {
            "lead_id": str(lead_id),
            "deleted": True,
            "type": "soft",
            "message": "Lead marked as deleted.",
        }


@router.post(
    "/{lead_id}/qualify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-run AI qualification on an existing lead",
)
async def requalify_lead(
    lead_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Trigger a fresh qualification run (scoring + AI analysis) on an existing
    lead.  Useful after manually editing lead fields or when the OpenAI
    model is updated.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found.",
        )

    # Reset status to "processing" while the background task runs
    lead.qualification_status = "processing"
    lead.updated_at = _utcnow()

    await _log_activity(
        db,
        lead.id,
        "requalification_triggered",
        "Manual re-qualification triggered via API.",
    )
    await db.commit()

    background_tasks.add_task(_run_qualification, lead_id)

    logger.info("Re-qualification triggered for lead %s.", lead_id)
    return {
        "lead_id": str(lead_id),
        "status": "processing",
        "message": "Re-qualification is running in the background.",
    }


@router.post(
    "/{lead_id}/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-sync lead to all configured integrations",
)
async def sync_lead_integrations(
    lead_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Push the lead to all enabled external integrations (Google Sheets,
    Airtable, HubSpot, n8n) without re-running AI qualification.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found.",
        )

    lead_dict = _lead_to_dict(lead)

    await _log_activity(
        db,
        lead.id,
        "sync_triggered",
        "Manual integration sync triggered via API.",
    )
    await db.commit()

    async def _do_sync(lid: uuid.UUID, ld: dict[str, Any]) -> None:
        from app.database import _get_session_factory  # noqa: PLC0415

        fac = _get_session_factory()
        async with fac() as session:
            try:
                settings = get_settings()

                if settings.GOOGLE_SHEETS_ENABLED:
                    try:
                        from app.services.google_sheets_service import GoogleSheetsService  # noqa: PLC0415

                        res = await GoogleSheetsService().sync_lead(ld)
                        await _record_integration_sync(session, lid, "google_sheets", res)
                        await _log_activity(session, lid, "crm_synced", f"Google Sheets re-sync: {res.get('status')}.", res)
                        await session.commit()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Re-sync Google Sheets failed for lead %s: %s", lid, exc)

                if settings.AIRTABLE_ENABLED:
                    try:
                        from app.services.airtable_service import AirtableService  # noqa: PLC0415

                        res = await AirtableService().sync_lead(ld)
                        await _record_integration_sync(session, lid, "airtable", res)
                        await _log_activity(session, lid, "crm_synced", f"Airtable re-sync: {res.get('status')}.", res)
                        await session.commit()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Re-sync Airtable failed for lead %s: %s", lid, exc)

                if settings.HUBSPOT_ENABLED:
                    try:
                        from app.services.crm_service import CRMService  # noqa: PLC0415

                        res = await CRMService().sync_lead(ld)
                        await _record_integration_sync(session, lid, "hubspot", res)
                        await _log_activity(session, lid, "crm_synced", f"HubSpot re-sync: {res.get('status')}.", res)
                        await session.commit()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Re-sync HubSpot failed for lead %s: %s", lid, exc)

                if settings.N8N_WEBHOOK_ENABLED:
                    try:
                        from app.services.n8n_service import N8NService  # noqa: PLC0415

                        res = await N8NService().send_lead_webhook(
                            lead_data=ld,
                            score=ld.get("score", 0),
                            status=ld.get("status", "unknown"),
                            ai_analysis={},
                        )
                        await _log_activity(session, lid, "n8n_webhook_sent", f"n8n re-sync: {res.get('status')}.", res)
                        await session.commit()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Re-sync n8n failed for lead %s: %s", lid, exc)

            except Exception as exc:  # noqa: BLE001
                logger.exception("Unhandled error in _do_sync for lead %s: %s", lid, exc)

    background_tasks.add_task(_do_sync, lead_id, lead_dict)

    return {
        "lead_id": str(lead_id),
        "status": "syncing",
        "message": "Integration sync is running in the background.",
    }


@router.post(
    "/{lead_id}/notify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-send Slack notification for a lead",
)
async def notify_lead(
    lead_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Re-send the Slack notification for an existing lead.

    Hot leads receive a rich block-kit message; warm leads receive a
    compact message.  Cold and unqualified leads are silently skipped.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found.",
        )

    lead_dict = _lead_to_dict(lead)
    final_score: int = lead.score or 0
    final_status: str = lead.qualification_status or "unqualified"
    recommended_action: str = lead.recommended_next_action or "Review the lead."

    await _log_activity(
        db,
        lead.id,
        "notification_triggered",
        "Manual Slack notification triggered via API.",
    )
    await db.commit()

    async def _do_notify(
        lid: uuid.UUID,
        ld: dict[str, Any],
        score: int,
        qs: str,
        action: str,
    ) -> None:
        from app.database import _get_session_factory  # noqa: PLC0415

        fac = _get_session_factory()
        async with fac() as session:
            try:
                settings = get_settings()
                if not settings.SLACK_WEBHOOK_URL:
                    logger.warning("Slack notification skipped: SLACK_WEBHOOK_URL not set.")
                    return

                from app.services.slack_service import SlackService  # noqa: PLC0415

                slack = SlackService()
                dashboard_url = f"{settings.APP_BASE_URL}/leads/{lid}"
                sent = False

                if qs == "hot":
                    sent = await slack.notify_hot_lead(
                        lead_data=ld,
                        score=score,
                        status=qs,
                        recommended_action=action,
                        dashboard_url=dashboard_url,
                    )
                elif qs == "warm":
                    sent = await slack.notify_warm_lead(lead_data=ld, score=score)

                if sent:
                    await _log_activity(
                        session,
                        lid,
                        "slack_notified",
                        f"Slack re-notification sent for {qs} lead.",
                        {"score": score, "status": qs},
                    )
                    await session.commit()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unhandled error in _do_notify for lead %s: %s", lid, exc)

    background_tasks.add_task(
        _do_notify, lead_id, lead_dict, final_score, final_status, recommended_action
    )

    return {
        "lead_id": str(lead_id),
        "status": "notifying",
        "message": "Slack notification is being sent in the background.",
    }
