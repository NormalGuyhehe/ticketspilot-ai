"""Webhook API integration tests."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from app.app import TicketsPilotApplication
from app.database.models import TicketStatus
from tests.fakes import FakeLLMClient
from tests.helpers import confident_ai, low_ai


def webhook_payload(external_id: str) -> dict:
    return {
        "external_id": external_id,
        "customer_email": "user@example.com",
        "subject": "Cannot login",
        "body": "I cannot login to my account.",
    }


async def test_webhook_requires_auth(client: AsyncClient):
    response = await client.post("/webhooks/tickets", json=webhook_payload("auth-1"))
    assert response.status_code == 403


async def test_webhook_rejects_invalid_key(
    client: AsyncClient,
):
    response = await client.post(
        "/webhooks/tickets",
        json=webhook_payload("auth-2"),
        headers={"X-Webhook-API-Key": "wrong"},
    )
    assert response.status_code == 403


async def test_webhook_validation_error(
    client: AsyncClient,
    webhook_headers: dict[str, str],
):
    response = await client.post(
        "/webhooks/tickets",
        json={"external_id": "valid-1"},
        headers=webhook_headers,
    )
    assert response.status_code == 422


async def test_webhook_invalid_email_returns_422(
    client: AsyncClient,
    webhook_headers: dict[str, str],
):
    payload = webhook_payload("invalid-email")
    payload["customer_email"] = "not-email"

    response = await client.post(
        "/webhooks/tickets",
        json=payload,
        headers=webhook_headers,
    )

    assert response.status_code == 422


async def test_webhook_creates_ticket_and_schedules_background_once(
    client: AsyncClient,
    application: TicketsPilotApplication,
    webhook_headers: dict[str, str],
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[int] = []

    async def fake_background(ticket_id: int) -> None:
        calls.append(ticket_id)

    monkeypatch.setattr(
        application.container,
        "process_ticket_background",
        fake_background,
    )

    response = await client.post(
        "/webhooks/tickets",
        json=webhook_payload("schedule-1"),
        headers=webhook_headers,
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == TicketStatus.RECEIVED.value
    assert calls == [data["id"]]

    ticket_response = await client.get(
        f"/tickets/{data['id']}",
        headers=admin_headers,
    )
    assert ticket_response.status_code == 200
    assert ticket_response.json()["external_id"] == "schedule-1"


async def test_webhook_is_idempotent_and_does_not_reschedule(
    client: AsyncClient,
    application: TicketsPilotApplication,
    webhook_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[int] = []

    async def fake_background(ticket_id: int) -> None:
        calls.append(ticket_id)

    monkeypatch.setattr(
        application.container,
        "process_ticket_background",
        fake_background,
    )

    payload = webhook_payload("idempotent-1")

    first = await client.post(
        "/webhooks/tickets",
        json=payload,
        headers=webhook_headers,
    )
    second = await client.post(
        "/webhooks/tickets",
        json=payload,
        headers=webhook_headers,
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert calls == [first.json()["id"]]


async def test_webhook_full_flow_auto_routes_confident_ticket(
    client: AsyncClient,
    application: TicketsPilotApplication,
    llm_client: FakeLLMClient,
    webhook_headers: dict[str, str],
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    llm_client.response = confident_ai()

    processed = asyncio.Event()
    original = application.container.process_ticket_background

    async def tracked_background(ticket_id: int) -> None:
        await original(ticket_id)
        processed.set()

    monkeypatch.setattr(
        application.container,
        "process_ticket_background",
        tracked_background,
    )

    response = await client.post(
        "/webhooks/tickets",
        json=webhook_payload("flow-auto"),
        headers=webhook_headers,
    )

    assert response.status_code == 202
    ticket_id = response.json()["id"]

    await asyncio.wait_for(processed.wait(), timeout=5)

    ticket_response = await client.get(
        f"/tickets/{ticket_id}",
        headers=admin_headers,
    )

    assert ticket_response.status_code == 200
    data = ticket_response.json()
    assert data["status"] == TicketStatus.AUTO_ROUTED.value
    assert data["assigned_to"] == "tech-support@example.com"
    assert data["ai_category"] == "Technical"
    assert data["ai_urgency"] == "High"
    assert data["ai_confidence"] == 92


async def test_webhook_full_flow_manual_review_low_confidence(
    client: AsyncClient,
    application: TicketsPilotApplication,
    llm_client: FakeLLMClient,
    webhook_headers: dict[str, str],
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    llm_client.response = low_ai()

    processed = asyncio.Event()
    original = application.container.process_ticket_background

    async def tracked_background(ticket_id: int) -> None:
        await original(ticket_id)
        processed.set()

    monkeypatch.setattr(
        application.container,
        "process_ticket_background",
        tracked_background,
    )

    response = await client.post(
        "/webhooks/tickets",
        json=webhook_payload("flow-manual"),
        headers=webhook_headers,
    )

    assert response.status_code == 202
    ticket_id = response.json()["id"]

    await asyncio.wait_for(processed.wait(), timeout=5)

    ticket_response = await client.get(
        f"/tickets/{ticket_id}",
        headers=admin_headers,
    )

    assert ticket_response.status_code == 200
    data = ticket_response.json()
    assert data["status"] == TicketStatus.MANUAL_REVIEW.value
    assert data["ai_confidence"] == 50
    assert data["ai_summary"] == "Ambiguous request"
