from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, field_serializer


class FollowUpEmailResponse(BaseModel):
    """Schema for serializing a FollowUpEmail record."""

    id: Any  # UUID, serialized as str
    lead_id: Any  # UUID, serialized as str
    subject: str
    body: str
    status: str  # e.g. "pending", "approved", "sent", "failed"
    ai_generated: bool
    approved_by: Optional[str] = None
    approved_at: Any = None  # datetime, serialized as ISO string
    sent_at: Any = None  # datetime, serialized as ISO string
    created_at: Any  # datetime, serialized as ISO string
    updated_at: Any = None  # datetime, serialized as ISO string

    model_config = {"from_attributes": True}

    @field_serializer("id", "lead_id")
    def serialize_uuid(self, value: Any) -> Optional[str]:
        if isinstance(value, UUID):
            return str(value)
        return str(value) if value is not None else None

    @field_serializer("approved_at", "sent_at", "created_at", "updated_at")
    def serialize_datetime(self, value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value) if value is not None else None


class FollowUpEmailUpdate(BaseModel):
    """Schema for editing draft email content before approval."""

    subject: Optional[str] = None
    body: Optional[str] = None

    model_config = {"str_strip_whitespace": True}


class EmailApprovalRequest(BaseModel):
    """Schema for approving a follow-up email draft."""

    approved_by: str

    model_config = {"str_strip_whitespace": True}


class EmailSendRequest(BaseModel):
    """Schema for triggering the sending of an approved email."""

    approved_by: Optional[str] = None

    model_config = {"str_strip_whitespace": True}
