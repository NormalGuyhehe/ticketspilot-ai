"""Pydantic schemas for AI classification responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

ALLOWED_CATEGORIES = {
    "Billing",
    "Technical",
    "General",
    "Feature",
    "Bug",
}

ALLOWED_URGENCIES = {
    "Low",
    "Medium",
    "High",
}

CATEGORY_ALIASES = {
    "bill": "Billing",
    "billing": "Billing",
    "payment": "Billing",
    "invoice": "Billing",
    "refund": "Billing",
    "tech": "Technical",
    "technical": "Technical",
    "support": "Technical",
    "issue": "Technical",
    "problem": "Technical",
    "general": "General",
    "question": "General",
    "info": "General",
    "feature": "Feature",
    "feature_request": "Feature",
    "enhancement": "Feature",
    "request": "Feature",
    "bug": "Bug",
    "error": "Bug",
    "defect": "Bug",
    "fault": "Bug",
}

URGENCY_ALIASES = {
    "low": "Low",
    "minor": "Low",
    "medium": "Medium",
    "normal": "Medium",
    "moderate": "Medium",
    "mid": "Medium",
    "high": "High",
    "urgent": "High",
    "critical": "High",
    "emergency": "High",
}


def _normalize_token(value: Any, aliases: dict[str, str], allowed: set[str]) -> str:
    raw = str(value).strip()
    if not raw:
        raise ValueError("empty value")

    key = raw.lower().replace("-", "_").replace(" ", "_")

    normalized = aliases.get(key)
    if normalized is None:
        for token in key.split("_"):
            if token in aliases:
                normalized = aliases[token]
                break

    if normalized is None:
        normalized = raw.title()

    if normalized not in allowed:
        raise ValueError(f"unsupported value: {raw}")

    return normalized


class AIClassificationResult(BaseModel):
    category: str = Field(
        ...,
        description="Ticket category: Billing | Technical | General | Feature | Bug",
    )
    urgency: str = Field(
        ...,
        description="Urgency level: Low | Medium | High",
    )
    summary: str = Field(
        ...,
        max_length=200,
        description="Brief summary of the issue",
    )
    confidence: int = Field(
        ...,
        ge=0,
        le=100,
        description="Model confidence 0-100",
    )
    requires_human_review: bool = Field(
        default=False,
        description="Whether human review is required",
    )
    missing_context: list[str] = Field(
        default_factory=list,
        description="List of missing information needed to resolve",
    )

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, value: Any) -> str:
        return _normalize_token(value, CATEGORY_ALIASES, ALLOWED_CATEGORIES)

    @field_validator("urgency", mode="before")
    @classmethod
    def validate_urgency(cls, value: Any) -> str:
        return _normalize_token(value, URGENCY_ALIASES, ALLOWED_URGENCIES)

    @field_validator("missing_context", mode="before")
    @classmethod
    def normalize_missing_context(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value]
        return []
