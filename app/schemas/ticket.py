"""Pydantic schemas for tickets."""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.database.models import ReviewDecision, TicketStatus


class TicketCreate(BaseModel):
    external_id: str = Field(..., max_length=255)
    customer_email: EmailStr
    subject: str = Field(..., max_length=500)
    body: str


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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: list[TicketOut]
    total: int
    page: int
    limit: int


class ReviewAction(BaseModel):
    reviewer_email: EmailStr
    comment: str | None = None
