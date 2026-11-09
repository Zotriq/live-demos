from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Float, Integer, Text, String, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Base):
    """
    Core lead record created when a prospect submits the contact / intake form.

    All AI-generated artefacts (score, qualification status, email drafts, etc.)
    are stored directly on this record or in related tables.
    """

    __tablename__ = "leads"

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Contact info
    # ------------------------------------------------------------------ #
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ------------------------------------------------------------------ #
    # Company / role
    # ------------------------------------------------------------------ #
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ------------------------------------------------------------------ #
    # Project / engagement details
    # ------------------------------------------------------------------ #
    budget: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_budget_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    normalized_budget_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timeline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ------------------------------------------------------------------ #
    # Raw submission payload
    # ------------------------------------------------------------------ #
    raw_payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # ------------------------------------------------------------------ #
    # AI qualification output
    # ------------------------------------------------------------------ #
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    qualification_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    ai_analysis_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    recommended_next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    follow_up_emails: Mapped[list["FollowUpEmail"]] = relationship(  # noqa: F821
        "FollowUpEmail",
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="select",
    )
    activities: Mapped[list["LeadActivity"]] = relationship(  # noqa: F821
        "LeadActivity",
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="select",
    )
    integration_syncs: Mapped[list["IntegrationSync"]] = relationship(  # noqa: F821
        "IntegrationSync",
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Lead id={self.id} email={self.email!r} "
            f"score={self.score} status={self.qualification_status!r}>"
        )
