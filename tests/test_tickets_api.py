"""Ticket query API tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.app import TicketsPilotApplication
from app.database.models import TicketStatus
from tests.helpers import create_ticket_with_history, seed_ticket


async def test_list_tickets_requires_admin_auth(client: AsyncClient):
    response = await client.get("/tickets")
    assert response.status_code == 403


async def test_list_tickets_empty(client: AsyncClient, admin_headers: dict[str, str]):
    response = await client.get("/tickets", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["limit"] == 20


async def test_list_tickets_pagination_and_filter(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    now = datetime.now(UTC)

    id_old = await seed_ticket(
        application,
        "api-page-old",
        status=TicketStatus.RECEIVED,
        created_at=now - timedelta(minutes=3),
    )
    id_mid = await seed_ticket(
        application,
        "api-page-mid",
        status=TicketStatus.RECEIVED,
        created_at=now - timedelta(minutes=2),
    )
    id_new = await seed_ticket(
        application,
        "api-page-new",
        status=TicketStatus.MANUAL_REVIEW,
        created_at=now - timedelta(minutes=1),
    )

    response = await client.get(
        "/tickets?page=1&limit=2",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert [item["id"] for item in data["items"]] == [id_new, id_mid]

    filtered = await client.get(
        "/tickets?status=RECEIVED",
        headers=admin_headers,
    )

    assert filtered.status_code == 200
    filtered_data = filtered.json()
    assert filtered_data["total"] == 2
    assert {item["id"] for item in filtered_data["items"]} == {id_old, id_mid}


async def test_list_tickets_validates_bounds(
    client: AsyncClient,
    admin_headers: dict[str, str],
):
    page_zero = await client.get("/tickets?page=0", headers=admin_headers)
    assert page_zero.status_code == 422

    limit_too_big = await client.get("/tickets?limit=101", headers=admin_headers)
    assert limit_too_big.status_code == 422


async def test_get_ticket_not_found(
    client: AsyncClient,
    admin_headers: dict[str, str],
):
    response = await client.get("/tickets/99999", headers=admin_headers)
    assert response.status_code == 404


async def test_get_ticket_success(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    ticket_id = await seed_ticket(application, "api-get-1")

    response = await client.get(
        f"/tickets/{ticket_id}",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == ticket_id
    assert data["external_id"] == "api-get-1"
    assert data["status"] == TicketStatus.RECEIVED.value


async def test_get_ticket_history(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    ticket_id = await create_ticket_with_history(application, "api-history-1")

    response = await client.get(
        f"/tickets/{ticket_id}/history",
        headers=admin_headers,
    )

    assert response.status_code == 200
    history = response.json()

    assert len(history) == 2
    assert history[0]["action"] == "CREATED"
    assert history[1]["action"] == "STATUS_CHANGED"
    assert history[1]["new_value"] == TicketStatus.PROCESSING.value
