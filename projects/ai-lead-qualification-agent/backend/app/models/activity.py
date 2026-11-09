from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LeadActivity(Base):
    """
    Audit / activity log for a :class:`Lead`.

    Each row represents a discrete event in the lead's lifecycle, for example:

    * ``lead_created``       – form submission received
    * ``ai_analysis_done``   – GPT qualification completed
    * ``email_drafted``      – follow-up email generated
    * ``email_sent``         – email delivered to the prospect
    * ``slack_notified``     – Slack message sent to the sales team
    * ``crm_synced``         – record pushed to HubSpot / Airtable / Sheets
    * ``status_changed``     – qualification status updated manually
    """

    __tablename__ = "lead_activities"

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
    # Event data
    # ------------------------------------------------------------------ #
    activity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # ------------------------------------------------------------------ #
    # Timestamp (immutable – activities are never updated)
    # ------------------------------------------------------------------ #
    created_at: Mapped[datetime] = mapped_column(
        default=_utcnow,
        server_default=func.now(),
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    lead: Mapped["Lead"] = relationship(  # noqa: F821
        "Lead",
        back_populates="activities",
        lazy="select",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<LeadActivity id={self.id} lead_id={self.lead_id} "
            f"type={self.activity_type!r}>"
        )
