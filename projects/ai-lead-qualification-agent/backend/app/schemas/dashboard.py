from __future__ import annotations

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    """Aggregate statistics shown on the main dashboard."""

    total_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    unqualified_leads: int
    average_score: float
    conversion_ready: int  # leads deemed ready for a sales follow-up


class LeadsByStatus(BaseModel):
    """Breakdown of leads grouped by qualification status."""

    status: str
    count: int


class LeadsBySource(BaseModel):
    """Breakdown of leads grouped by acquisition source."""

    source: str
    count: int
