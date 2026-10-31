"""Pydantic schemas for tickets."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.database.models import ReviewDecision, TicketStatus


class TicketCreate(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=255)
    customer_email: EmailStr
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=10_000)


class TicketOut(BaseModel):
    id: int
    external_id: str
    customer_email: str
    subject: str
    status: TicketStatus
    ai_category: str | None = None
    ai_urgency: str | None = None
    ai_summary: str | None = None
    ai_confidence: int | None = None
    assigned_to: str | None = None
    reviewed_by: str | None = None
    review_decision: ReviewDecision | None = None
    review_comment: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: list[TicketOut]
    total: int
    page: int
    limit: int


class TicketHistoryOut(BaseModel):
    id: int
    action: str
    old_value: str | None = None
    new_value: str | None = None
    actor: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class ReviewAction(BaseModel):
    reviewer_email: EmailStr
    comment: str | None = None
