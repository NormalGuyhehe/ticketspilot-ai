"""Pydantic schemas for AI classification responses."""
from pydantic import BaseModel, Field


class AIClassificationResult(BaseModel):
    category: str = Field(..., description="Ticket category: Billing | Technical | General | Feature | Bug")
    urgency: str = Field(..., description="Urgency level: Low | Medium | High")
    summary: str = Field(..., max_length=200, description="Brief summary of the issue")
    confidence: int = Field(..., ge=0, le=100, description="Model confidence 0-100")
    requires_human_review: bool = Field(
        default=False,
        description="Whether human review is required",
    )
    missing_context: list[str] = Field(
        default_factory=list,
        description="List of missing information needed to resolve",
    )
