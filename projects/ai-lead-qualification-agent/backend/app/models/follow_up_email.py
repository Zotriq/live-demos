from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FollowUpEmail(Base):
    """
    AI-generated (or human-edited) follow-up email draft associated with a Lead.

    Lifecycle:
    ``draft_generated`` → ``approved`` (by a human reviewer) → ``sent``

    A lead can have multiple follow-up emails (e.g. initial outreach,
    a follow-up reminder, a proposal summary, etc.).
    """

    __tablename__ = "follow_up_emails"

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Foreign key
    # ------------------------------------------------------------------ #
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Email content
    # ------------------------------------------------------------------ #
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ------------------------------------------------------------------ #
    # Workflow state
    # ------------------------------------------------------------------ #
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft_generated",
        server_default="draft_generated",
        index=True,
    )
    ai_generated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # ------------------------------------------------------------------ #
    # Approval tracking
    # ------------------------------------------------------------------ #
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ------------------------------------------------------------------ #
    # Delivery tracking
    # ------------------------------------------------------------------ #
    sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ------------------------------------------------------------------ #
    # Timestamps
    # ------------------------------------------------------------------ #
    created_at: Mapped[datetime] = mapped_column(
        default=_utcnow,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    lead: Mapped["Lead"] = relationship(  # noqa: F821
        "Lead",
        back_populates="follow_up_emails",
        lazy="select",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<FollowUpEmail id={self.id} lead_id={self.lead_id} "
            f"status={self.status!r}>"
        )
