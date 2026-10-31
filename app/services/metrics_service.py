"""Metrics business logic."""

from __future__ import annotations

from datetime import UTC, datetime

from app.database.models import ReviewDecision, TicketStatus
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.admin import (
    MetricsAccuracy,
    MetricsProcessingTime,
    MetricsSummary,
)


class MetricsService:
    def __init__(self, repo: MetricsRepository) -> None:
        self._repo = repo

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    async def summary(self) -> MetricsSummary:
        counts = await self._repo.status_counts()

        total = sum(counts.values())
        resolved = counts.get(TicketStatus.RESOLVED, 0)

        return MetricsSummary(
            total_tickets=total,
            received=counts.get(TicketStatus.RECEIVED, 0),
            processing=counts.get(TicketStatus.PROCESSING, 0),
            auto_routed=counts.get(TicketStatus.AUTO_ROUTED, 0),
            manual_review=counts.get(TicketStatus.MANUAL_REVIEW, 0),
            resolved=resolved,
            auto_resolution_rate=(resolved / total * 100) if total else 0.0,
        )

    async def accuracy(self) -> MetricsAccuracy:
        counts = await self._repo.review_counts()

        approved = counts.get(ReviewDecision.APPROVED, 0)
        rejected = counts.get(ReviewDecision.REJECTED, 0)
        total = approved + rejected

        return MetricsAccuracy(
            total_reviewed=total,
            approved=approved,
            rejected=rejected,
            accuracy_rate=(approved / total * 100) if total else 0.0,
        )

    async def processing_time(self) -> MetricsProcessingTime:
        intervals = await self._repo.resolved_intervals()

        if not intervals:
            return MetricsProcessingTime(
                avg_processing_seconds=0.0,
                min_processing_seconds=0.0,
                max_processing_seconds=0.0,
            )

        seconds: list[float] = []

        for created_at, resolved_at in intervals:
            created = self._ensure_aware(created_at)
            resolved = self._ensure_aware(resolved_at)
            delta = (resolved - created).total_seconds()
            if delta >= 0:
                seconds.append(delta)

        if not seconds:
            return MetricsProcessingTime(
                avg_processing_seconds=0.0,
                min_processing_seconds=0.0,
                max_processing_seconds=0.0,
            )

        return MetricsProcessingTime(
            avg_processing_seconds=sum(seconds) / len(seconds),
            min_processing_seconds=min(seconds),
            max_processing_seconds=max(seconds),
        )
