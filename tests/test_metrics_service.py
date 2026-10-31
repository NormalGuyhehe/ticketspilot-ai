"""Metrics service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ReviewDecision, Ticket, TicketStatus
from app.repositories.metrics_repository import MetricsRepository
from app.services.metrics_service import MetricsService


async def add_ticket(
    db: AsyncSession,
    external_id: str,
    status: TicketStatus,
    *,
    review_decision: ReviewDecision | None = None,
    created_at: datetime | None = None,
    resolved_at: datetime | None = None,
) -> Ticket:
    ticket = Ticket(
        external_id=external_id,
        customer_email="user@example.com",
        subject="Metric",
        body="Metric body",
        status=status,
        review_decision=review_decision,
        created_at=created_at or datetime.now(UTC),
        resolved_at=resolved_at,
    )
    db.add(ticket)
    await db.flush()
    return ticket


async def test_summary_counts_and_rate(db_session: AsyncSession):
    await add_ticket(db_session, "m-1", TicketStatus.RECEIVED)
    await add_ticket(db_session, "m-2", TicketStatus.MANUAL_REVIEW)
    await add_ticket(db_session, "m-3", TicketStatus.RESOLVED)

    service = MetricsService(MetricsRepository(db_session))
    summary = await service.summary()

    assert summary.total_tickets == 3
    assert summary.received == 1
    assert summary.manual_review == 1
    assert summary.resolved == 1
    assert summary.auto_resolution_rate == pytest.approx(33.3333333, rel=1e-3)


async def test_accuracy_counts_reviews(db_session: AsyncSession):
    await add_ticket(
        db_session,
        "acc-1",
        TicketStatus.APPROVED,
        review_decision=ReviewDecision.APPROVED,
    )
    await add_ticket(
        db_session,
        "acc-2",
        TicketStatus.REJECTED,
        review_decision=ReviewDecision.REJECTED,
    )

    service = MetricsService(MetricsRepository(db_session))
    accuracy = await service.accuracy()

    assert accuracy.total_reviewed == 2
    assert accuracy.approved == 1
    assert accuracy.rejected == 1
    assert accuracy.accuracy_rate == pytest.approx(50.0)


async def test_processing_time_empty(db_session: AsyncSession):
    service = MetricsService(MetricsRepository(db_session))
    metrics = await service.processing_time()

    assert metrics.avg_processing_seconds == 0.0
    assert metrics.min_processing_seconds == 0.0
    assert metrics.max_processing_seconds == 0.0


async def test_processing_time_calculates_intervals(db_session: AsyncSession):
    now = datetime.now(UTC)

    await add_ticket(
        db_session,
        "time-1",
        TicketStatus.RESOLVED,
        created_at=now - timedelta(seconds=10),
        resolved_at=now,
    )

    await add_ticket(
        db_session,
        "time-2",
        TicketStatus.RESOLVED,
        created_at=now - timedelta(seconds=20),
        resolved_at=now,
    )

    service = MetricsService(MetricsRepository(db_session))
    metrics = await service.processing_time()

    assert metrics.min_processing_seconds == pytest.approx(10.0, abs=0.5)
    assert metrics.max_processing_seconds == pytest.approx(20.0, abs=0.5)
    assert metrics.avg_processing_seconds == pytest.approx(15.0, abs=0.5)
