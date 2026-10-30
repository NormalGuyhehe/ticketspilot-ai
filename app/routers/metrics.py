"""Metrics and analytics endpoints."""
from fastapi import APIRouter

from app.schemas.admin import MetricsAccuracy, MetricsProcessingTime, MetricsSummary

router = APIRouter()


@router.get("/summary", response_model=MetricsSummary)
async def get_summary():
    # TODO: Implement
    raise NotImplementedError


@router.get("/accuracy", response_model=MetricsAccuracy)
async def get_accuracy():
    # TODO: Implement
    raise NotImplementedError


@router.get("/processing-time", response_model=MetricsProcessingTime)
async def get_processing_time():
    # TODO: Implement
    raise NotImplementedError
