"""Metrics API tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.app import TicketsPilotApplication
from app.database.models import ReviewDecision, TicketStatus
from tests.helpers import seed_ticket


async def test_metrics_require_auth(client: AsyncClient):
    response = await client.get("/metrics/summary")
    assert response.status_code == 403


async def test_metrics_summary(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    await seed_ticket(application, "metric-sum-1", status=TicketStatus.RECEIVED)
    await seed_ticket(application, "metric-sum-2", status=TicketStatus.MANUAL_REVIEW)
    await seed_ticket(application, "metric-sum-3", status=TicketStatus.RESOLVED)

    response = await client.get("/metrics/summary", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_tickets"] == 3
    assert data["received"] == 1
    assert data["manual_review"] == 1
    assert data["resolved"] == 1
    assert data["auto_resolution_rate"] == pytest.approx(33.3333333, rel=1e-3)


async def test_metrics_accuracy(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    await seed_ticket(
        application,
        "metric-acc-1",
        status=TicketStatus.APPROVED,
        review_decision=ReviewDecision.APPROVED,
    )
    await seed_ticket(
        application,
        "metric-acc-2",
        status=TicketStatus.REJECTED,
        review_decision=ReviewDecision.REJECTED,
    )

    response = await client.get("/metrics/accuracy", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_reviewed"] == 2
    assert data["approved"] == 1
    assert data["rejected"] == 1
    assert data["accuracy_rate"] == pytest.approx(50.0)


async def test_metrics_processing_time(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    now = datetime.now(UTC)

    await seed_ticket(
        application,
        "metric-time-1",
        status=TicketStatus.RESOLVED,
        created_at=now - timedelta(seconds=10),
        resolved_at=now,
    )

    await seed_ticket(
        application,
        "metric-time-2",
        status=TicketStatus.RESOLVED,
        created_at=now - timedelta(seconds=20),
        resolved_at=now,
    )

    response = await client.get("/metrics/processing-time", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["min_processing_seconds"] == pytest.approx(10.0, abs=0.5)
    assert data["max_processing_seconds"] == pytest.approx(20.0, abs=0.5)
    assert data["avg_processing_seconds"] == pytest.approx(15.0, abs=0.5)
