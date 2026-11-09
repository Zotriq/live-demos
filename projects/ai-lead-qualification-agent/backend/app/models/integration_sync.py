from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IntegrationSync(Base):
    """
    Tracks the synchronisation status of a :class:`Lead` to an external
    integration (HubSpot, Airtable, Google Sheets, n8n, etc.).

    One row is written per lead-per-integration attempt so that the full
    sync history is preserved and retries can be tracked.

    Possible ``sync_status`` values:
    * ``pending``   – queued, not yet attempted
    * ``success``   – record successfully pushed to the external system
    * ``failed``    – push attempted but rejected / errored
    * ``skipped``   – integration disabled at the time of the attempt
    """

    __tablename__ = "integration_syncs"

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
    # Sync metadata
    # ------------------------------------------------------------------ #
    integration_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    sync_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="ID of the corresponding record in the external system.",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ------------------------------------------------------------------ #
    # Timing
    # ------------------------------------------------------------------ #
    synced_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Timestamp of the last successful sync.",
    )
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
        back_populates="integration_syncs",
        lazy="select",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IntegrationSync id={self.id} lead_id={self.lead_id} "
            f"integration={self.integration_name!r} status={self.sync_status!r}>"
        )
