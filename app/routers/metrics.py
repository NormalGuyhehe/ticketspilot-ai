"""Metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import verify_admin_key
from app.dependencies import get_metrics_service
from app.schemas.admin import (
    MetricsAccuracy,
    MetricsProcessingTime,
    MetricsSummary,
)
from app.services.metrics_service import MetricsService

metrics_router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
    dependencies=[Depends(verify_admin_key)],
)


@metrics_router.get("/summary", response_model=MetricsSummary)
async def get_summary(
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> MetricsSummary:
    return await metrics_service.summary()


@metrics_router.get("/accuracy", response_model=MetricsAccuracy)
async def get_accuracy(
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> MetricsAccuracy:
    return await metrics_service.accuracy()


@metrics_router.get("/processing-time", response_model=MetricsProcessingTime)
async def get_processing_time(
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> MetricsProcessingTime:
    return await metrics_service.processing_time()
