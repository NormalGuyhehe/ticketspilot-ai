"""Pydantic schemas for admin operations."""
from pydantic import BaseModel


class MetricsSummary(BaseModel):
    total_tickets: int
    received: int
    processing: int
    auto_routed: int
    manual_review: int
    resolved: int
    auto_resolution_rate: float


class MetricsAccuracy(BaseModel):
    total_reviewed: int
    approved: int
    rejected: int
    accuracy_rate: float


class MetricsProcessingTime(BaseModel):
    avg_processing_seconds: float
    min_processing_seconds: float
    max_processing_seconds: float
