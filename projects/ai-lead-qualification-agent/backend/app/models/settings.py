from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Settings(Base):
    """
    Key-value store for runtime-configurable application settings.

    Values are stored as JSON so that any scalar type (string, number,
    boolean, list, object) can be persisted without schema changes.

    Examples
    --------
    * ``key="scoring_weights"``  → ``value_json={"budget": 30, "timeline": 20}``
    * ``key="qualification_thresholds"`` → ``value_json={"hot": 80, "warm": 50}``
    * ``key="notifications_enabled"`` → ``value_json=true``
    """

    __tablename__ = "settings"

    # ------------------------------------------------------------------ #
    # Identity  (integer PK – simpler for a small config table)
    # ------------------------------------------------------------------ #
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Setting record
    # ------------------------------------------------------------------ #
    key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    value_json: Mapped[Any] = mapped_column(JSON, nullable=False)

    # ------------------------------------------------------------------ #
    # Timestamp
    # ------------------------------------------------------------------ #
    updated_at: Mapped[datetime] = mapped_column(
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Settings id={self.id} key={self.key!r}>"
