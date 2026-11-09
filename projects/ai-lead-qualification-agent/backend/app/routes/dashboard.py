"""
Dashboard API router.

Provides aggregated statistics for the lead qualification dashboard.
All queries use SQLAlchemy async with ``func.count`` / ``func.avg`` so
they execute as a single round-trip per endpoint.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lead import Lead
from app.schemas.dashboard import DashboardSummary, LeadsBySource, LeadsByStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Aggregate dashboard statistics",
    response_description="Counts and averages across all leads.",
)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    """
    Return headline KPIs for the dashboard:

    - ``total_leads``         — total records in the leads table
    - ``hot_leads``           — leads with ``qualification_status = 'hot'``
    - ``warm_leads``          — leads with ``qualification_status = 'warm'``
    - ``cold_leads``          — leads with ``qualification_status = 'cold'``
    - ``unqualified_leads``   — leads with ``qualification_status = 'unqualified'``
    - ``average_score``       — mean ``score`` across all scored leads (0 if none)
    - ``conversion_ready``    — alias for hot_leads (leads ready for sales follow-up)

    Soft-deleted leads (``qualification_status = 'deleted'``) and leads
    currently in the ``'processing'`` state are excluded from status counts
    but included in the total and average score calculation.
    """
    # Single query: count total, count by status, average score
    stmt = select(
        # Total leads
        func.count(Lead.id).label("total_leads"),
        # Per-status counts using conditional aggregation
        func.count(
            case((Lead.qualification_status == "hot", Lead.id))
        ).label("hot_leads"),
        func.count(
            case((Lead.qualification_status == "warm", Lead.id))
        ).label("warm_leads"),
        func.count(
            case((Lead.qualification_status == "cold", Lead.id))
        ).label("cold_leads"),
        func.count(
            case((Lead.qualification_status == "unqualified", Lead.id))
        ).label("unqualified_leads"),
        # Average score (COALESCE to 0 when no rows have a score)
        func.coalesce(func.avg(Lead.score), 0).label("average_score"),
    )

    result = await db.execute(stmt)
    row = result.one()

    total_leads: int = row.total_leads or 0
    hot_leads: int = row.hot_leads or 0
    warm_leads: int = row.warm_leads or 0
    cold_leads: int = row.cold_leads or 0
    unqualified_leads: int = row.unqualified_leads or 0
    average_score: float = float(row.average_score or 0)

    return DashboardSummary(
        total_leads=total_leads,
        hot_leads=hot_leads,
        warm_leads=warm_leads,
        cold_leads=cold_leads,
        unqualified_leads=unqualified_leads,
        average_score=round(average_score, 2),
        conversion_ready=hot_leads,  # hot leads are conversion-ready
    )


@router.get(
    "/leads-by-status",
    summary="Lead count breakdown by qualification status",
    response_description="List of (status, count) pairs ordered by count descending.",
)
async def get_leads_by_status(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Return a list of ``{ status, count }`` objects representing the
    distribution of leads across all qualification statuses.

    Statuses with zero leads are omitted.  Results are ordered by count
    descending so the most populous bucket appears first.
    """
    stmt = (
        select(
            Lead.qualification_status.label("status"),
            func.count(Lead.id).label("count"),
        )
        .where(Lead.qualification_status.isnot(None))
        .group_by(Lead.qualification_status)
        .order_by(func.count(Lead.id).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        LeadsByStatus(status=row.status or "unknown", count=row.count).model_dump()
        for row in rows
    ]


@router.get(
    "/leads-by-source",
    summary="Lead count breakdown by acquisition source",
    response_description="List of (source, count) pairs ordered by count descending.",
)
async def get_leads_by_source(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Return a list of ``{ source, count }`` objects representing the
    distribution of leads across all acquisition sources (e.g. website_form,
    linkedin, referral, n8n_webhook, crm_webhook, etc.).

    Sources with zero leads are omitted.  Results are ordered by count
    descending.
    """
    stmt = (
        select(
            Lead.source.label("source"),
            func.count(Lead.id).label("count"),
        )
        .where(Lead.source.isnot(None))
        .group_by(Lead.source)
        .order_by(func.count(Lead.id).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        LeadsBySource(source=row.source or "unknown", count=row.count).model_dump()
        for row in rows
    ]
