"""
Email approval router.

Manages the follow-up email lifecycle for a lead:

  draft_generated  →  approved  →  sent
                   ↘  rejected

All endpoints are prefixed with ``/api/leads`` so they share the same
URL namespace as the core leads router (e.g. ``/api/leads/{id}/follow-up``).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.activity import LeadActivity
from app.models.follow_up_email import FollowUpEmail
from app.models.lead import Lead
from app.schemas.email import (
    EmailApprovalRequest,
    EmailSendRequest,
    FollowUpEmailResponse,
    FollowUpEmailUpdate,
)
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leads", tags=["Email Approval"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _get_lead_or_404(db: AsyncSession, lead_id: uuid.UUID) -> Lead:
    """Return the Lead or raise 404."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found.",
        )
    return lead


async def _get_latest_follow_up_or_404(
    db: AsyncSession, lead_id: uuid.UUID
) -> FollowUpEmail:
    """Return the most recently created FollowUpEmail for a lead or raise 404."""
    stmt = (
        select(FollowUpEmail)
        .where(FollowUpEmail.lead_id == lead_id)
        .order_by(FollowUpEmail.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    email = result.scalar_one_or_none()
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No follow-up email found for lead '{lead_id}'.",
        )
    return email


async def _log_activity(
    db: AsyncSession,
    lead_id: uuid.UUID,
    activity_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist a LeadActivity row, swallowing any errors."""
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
            "Failed to log activity '%s' for lead %s: %s", activity_type, lead_id, exc
        )


def _email_to_response(email: FollowUpEmail) -> dict[str, Any]:
    """Serialise a FollowUpEmail ORM instance to a response dict."""
    return {
        "id": str(email.id),
        "lead_id": str(email.lead_id),
        "subject": email.subject or "",
        "body": email.body or "",
        "status": email.status,
        "ai_generated": email.ai_generated,
        "approved_by": email.approved_by,
        "approved_at": email.approved_at.isoformat() if email.approved_at else None,
        "sent_at": email.sent_at.isoformat() if email.sent_at else None,
        "created_at": email.created_at.isoformat() if email.created_at else None,
        "updated_at": email.updated_at.isoformat() if email.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{lead_id}/follow-up",
    summary="Get the latest follow-up email for a lead",
    response_description="The most recently generated follow-up email draft.",
)
async def get_follow_up_email(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the most recently created ``FollowUpEmail`` record associated
    with the given lead.

    Raises ``404`` if the lead does not exist or has no follow-up emails yet.
    """
    # Validate lead exists
    await _get_lead_or_404(db, lead_id)

    email = await _get_latest_follow_up_or_404(db, lead_id)
    return _email_to_response(email)


@router.put(
    "/{lead_id}/follow-up",
    summary="Edit the follow-up email subject or body",
    response_description="Updated follow-up email record.",
)
async def update_follow_up_email(
    lead_id: uuid.UUID,
    payload: FollowUpEmailUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Update the ``subject`` and/or ``body`` of the latest follow-up email
    for a lead.

    Only the fields supplied in the request body are changed.  The email
    status is not altered by this endpoint — use ``/approve-email`` or
    ``/reject-email`` to change the approval state.
    """
    await _get_lead_or_404(db, lead_id)
    email = await _get_latest_follow_up_or_404(db, lead_id)

    changed_fields: list[str] = []

    if payload.subject is not None:
        email.subject = payload.subject
        changed_fields.append("subject")

    if payload.body is not None:
        email.body = payload.body
        changed_fields.append("body")

    if not changed_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update. Supply 'subject' and/or 'body'.",
        )

    email.updated_at = _utcnow()

    await _log_activity(
        db,
        lead_id,
        "email_edited",
        f"Follow-up email updated. Fields changed: {', '.join(changed_fields)}.",
        {"email_id": str(email.id), "changed_fields": changed_fields},
    )

    await db.commit()
    await db.refresh(email)

    logger.info(
        "FollowUpEmail %s updated for lead %s. Fields: %s",
        email.id,
        lead_id,
        changed_fields,
    )
    return _email_to_response(email)


@router.post(
    "/{lead_id}/approve-email",
    summary="Approve the follow-up email for sending",
    response_description="Follow-up email marked as approved.",
)
async def approve_email(
    lead_id: uuid.UUID,
    payload: EmailApprovalRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Mark the latest follow-up email as ``"approved"``.

    Records ``approved_by`` (the identifier of the approving user) and
    ``approved_at`` (current UTC timestamp).  Once approved the email can
    be dispatched via the ``/send-email`` endpoint.
    """
    await _get_lead_or_404(db, lead_id)
    email = await _get_latest_follow_up_or_404(db, lead_id)

    if email.status == "sent":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot approve an email that has already been sent.",
        )

    email.status = "approved"
    email.approved_by = payload.approved_by
    email.approved_at = _utcnow()
    email.updated_at = _utcnow()

    await _log_activity(
        db,
        lead_id,
        "email_approved",
        f"Follow-up email approved by '{payload.approved_by}'.",
        {"email_id": str(email.id), "approved_by": payload.approved_by},
    )

    await db.commit()
    await db.refresh(email)

    logger.info(
        "FollowUpEmail %s approved by '%s' for lead %s.",
        email.id,
        payload.approved_by,
        lead_id,
    )
    return _email_to_response(email)


@router.post(
    "/{lead_id}/reject-email",
    summary="Reject the follow-up email draft",
    response_description="Follow-up email marked as rejected.",
)
async def reject_email(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Mark the latest follow-up email as ``"rejected"``.

    A rejected email will not be sent.  A new draft can be generated by
    re-running qualification (``POST /{lead_id}/qualify``) or by editing
    and re-approving the existing draft.
    """
    await _get_lead_or_404(db, lead_id)
    email = await _get_latest_follow_up_or_404(db, lead_id)

    if email.status == "sent":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reject an email that has already been sent.",
        )

    email.status = "rejected"
    email.updated_at = _utcnow()

    await _log_activity(
        db,
        lead_id,
        "email_rejected",
        "Follow-up email rejected.",
        {"email_id": str(email.id)},
    )

    await db.commit()
    await db.refresh(email)

    logger.info("FollowUpEmail %s rejected for lead %s.", email.id, lead_id)
    return _email_to_response(email)


@router.post(
    "/{lead_id}/send-email",
    summary="Send the approved follow-up email",
    response_description="Delivery result and updated email record.",
)
async def send_email(
    lead_id: uuid.UUID,
    payload: EmailSendRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Dispatch the follow-up email to the lead's email address.

    **Requirements:**
    - The latest follow-up email must have ``status == "approved"``.
    - ``EMAIL_SENDING_ENABLED`` must be ``true`` in the application settings.
    - SMTP credentials must be configured.

    On success the email ``status`` is updated to ``"sent"`` and ``sent_at``
    is recorded.  If the email service returns a ``"skipped"`` status (i.e.
    email sending is disabled) the record is **not** marked as sent.
    """
    lead = await _get_lead_or_404(db, lead_id)
    email = await _get_latest_follow_up_or_404(db, lead_id)

    # Guard: only send approved emails
    if email.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Email cannot be sent: current status is '{email.status}'. "
                "Only emails with status 'approved' can be sent."
            ),
        )

    if not lead.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lead has no email address on record. Cannot send email.",
        )

    # ---- Attempt delivery ------------------------------------------------
    email_service = EmailService()
    result = await email_service.send_email(
        to_email=lead.email,
        subject=email.subject or "(No subject)",
        body=email.body or "",
    )

    send_status: str = result.get("status", "error")
    send_message: str = result.get("message", "")

    logger.info(
        "EmailService send attempt for lead %s (email_id=%s): status=%s",
        lead_id,
        email.id,
        send_status,
    )

    # ---- Persist outcome -------------------------------------------------
    if send_status == "success":
        email.status = "sent"
        email.sent_at = _utcnow()
        # If an approver override is supplied in the send request, record it
        if payload.approved_by and not email.approved_by:
            email.approved_by = payload.approved_by
            email.approved_at = email.approved_at or _utcnow()
        email.updated_at = _utcnow()

        await _log_activity(
            db,
            lead_id,
            "email_sent",
            f"Follow-up email '{email.subject}' sent to '{lead.email}'.",
            {
                "email_id": str(email.id),
                "recipient": lead.email,
                "subject": email.subject,
                "send_result": result,
            },
        )
        await db.commit()
        await db.refresh(email)

    elif send_status == "skipped":
        # Email sending is disabled; do not update the email record.
        await _log_activity(
            db,
            lead_id,
            "email_send_skipped",
            f"Email send skipped: {send_message}",
            {"email_id": str(email.id), "send_result": result},
        )
        await db.commit()

    else:
        # Delivery error — log but do not change email status so it can be retried.
        await _log_activity(
            db,
            lead_id,
            "email_send_failed",
            f"Email send failed: {send_message}",
            {"email_id": str(email.id), "send_result": result},
        )
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email delivery failed: {send_message}",
        )

    return {
        "email": _email_to_response(email),
        "send_result": result,
    }
