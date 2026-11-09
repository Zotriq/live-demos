from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_serializer, model_validator


class LeadIntakeRequest(BaseModel):
    """Schema for incoming lead form submissions."""

    name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    job_title: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    source: str = "website_form"
    message: Optional[str] = None
    project_type: Optional[str] = None
    country: Optional[str] = None

    model_config = {"str_strip_whitespace": True}


class LeadResponse(BaseModel):
    """Schema for serializing a Lead record from the database."""

    id: Any  # UUID stored as uuid.UUID, serialized as str
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    job_title: Optional[str] = None
    budget: Optional[str] = None
    normalized_budget_min: Optional[float] = None
    normalized_budget_max: Optional[float] = None
    timeline: Optional[str] = None
    source: Optional[str] = None
    message: Optional[str] = None
    project_type: Optional[str] = None
    country: Optional[str] = None
    score: Optional[int] = None
    qualification_status: Optional[str] = None
    ai_analysis_json: Optional[Any] = None
    recommended_next_action: Optional[str] = None
    created_at: Any  # datetime, serialized as ISO string
    updated_at: Any  # datetime, serialized as ISO string

    model_config = {"from_attributes": True}

    @field_serializer("id")
    def serialize_id(self, value: Any) -> Optional[str]:
        if isinstance(value, UUID):
            return str(value)
        return str(value) if value is not None else None

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value) if value is not None else None


class LeadListResponse(BaseModel):
    """Paginated list of leads."""

    leads: list[LeadResponse]
    total: int
    page: int
    page_size: int


class LeadUpdateRequest(BaseModel):
    """Schema for partial updates to an existing lead."""

    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    job_title: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    source: Optional[str] = None
    message: Optional[str] = None
    project_type: Optional[str] = None
    country: Optional[str] = None
    score: Optional[int] = None
    qualification_status: Optional[str] = None

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> "LeadUpdateRequest":
        values = self.model_dump(exclude_none=True)
        if not values:
            raise ValueError("At least one field must be provided for update.")
        return self


class LeadQualificationResponse(BaseModel):
    """Schema for returning AI qualification results."""

    score: int
    qualification_status: str  # e.g. "hot", "warm", "cold", "unqualified"
    ai_analysis: Optional[Any] = None
