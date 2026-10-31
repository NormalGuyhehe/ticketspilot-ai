"""Admin API integration tests."""

from __future__ import annotations

from httpx import AsyncClient

from app.app import TicketsPilotApplication
from app.database.models import ReviewDecision, TicketStatus
from tests.helpers import seed_ticket


def review_body(comment: str = "ok") -> dict:
    return {
        "reviewer_email": "operator@example.com",
        "comment": comment,
    }


async def test_admin_requires_auth(client: AsyncClient):
    response = await client.get("/admin/reviews")
    assert response.status_code == 403


async def test_list_reviews_returns_only_requested_status(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    manual_id = await seed_ticket(
        application,
        "admin-list-manual",
        status=TicketStatus.MANUAL_REVIEW,
    )
    await seed_ticket(
        application,
        "admin-list-received",
        status=TicketStatus.RECEIVED,
    )

    response = await client.get("/admin/reviews", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == manual_id
    assert data[0]["status"] == TicketStatus.MANUAL_REVIEW.value


async def test_approve_review(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    ticket_id = await seed_ticket(
        application,
        "admin-approve",
        status=TicketStatus.MANUAL_REVIEW,
    )

    response = await client.post(
        f"/admin/reviews/{ticket_id}/approve",
        json=review_body("Approved"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == TicketStatus.APPROVED.value
    assert data["reviewed_by"] == "operator@example.com"
    assert data["review_decision"] == ReviewDecision.APPROVED.value
    assert data["review_comment"] == "Approved"


async def test_reject_review(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    ticket_id = await seed_ticket(
        application,
        "admin-reject",
        status=TicketStatus.MANUAL_REVIEW,
    )

    response = await client.post(
        f"/admin/reviews/{ticket_id}/reject",
        json=review_body("Wrong category"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == TicketStatus.REJECTED.value
    assert data["review_decision"] == ReviewDecision.REJECTED.value


async def test_escalate_review(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    ticket_id = await seed_ticket(
        application,
        "admin-escalate",
        status=TicketStatus.MANUAL_REVIEW,
    )

    response = await client.post(
        f"/admin/reviews/{ticket_id}/escalate",
        json=review_body("Needs L2"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == TicketStatus.ESCALATED.value
    assert data["reviewed_by"] == "operator@example.com"
    assert data["review_comment"] == "Needs L2"


async def test_resolve_approved_ticket(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    ticket_id = await seed_ticket(
        application,
        "admin-resolve-approved",
        status=TicketStatus.APPROVED,
    )

    response = await client.post(
        f"/admin/tickets/{ticket_id}/resolve",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == TicketStatus.RESOLVED.value
    assert data["resolved_at"] is not None


async def test_invalid_transition_returns_400(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    ticket_id = await seed_ticket(
        application,
        "admin-invalid",
        status=TicketStatus.RECEIVED,
    )

    response = await client.post(
        f"/admin/tickets/{ticket_id}/resolve",
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert "Cannot transition" in response.json()["detail"]


async def test_approve_non_manual_ticket_returns_400(
    client: AsyncClient,
    application: TicketsPilotApplication,
    admin_headers: dict[str, str],
):
    ticket_id = await seed_ticket(
        application,
        "admin-approve-invalid",
        status=TicketStatus.RECEIVED,
    )

    response = await client.post(
        f"/admin/reviews/{ticket_id}/approve",
        json=review_body(),
        headers=admin_headers,
    )

    assert response.status_code == 400
