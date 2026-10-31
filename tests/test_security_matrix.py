"""Security matrix tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

ADMIN_GET_PATHS = [
    "/tickets",
    "/tickets/1",
    "/tickets/1/history",
    "/admin/reviews",
    "/metrics/summary",
    "/metrics/accuracy",
    "/metrics/processing-time",
]

ADMIN_POST_JSON_PATHS = [
    "/admin/reviews/1/approve",
    "/admin/reviews/1/reject",
    "/admin/reviews/1/escalate",
]

ADMIN_POST_NO_BODY_PATHS = [
    "/admin/tickets/1/resolve",
]


def review_body() -> dict:
    return {
        "reviewer_email": "operator@example.com",
        "comment": "test",
    }


def webhook_payload() -> dict:
    return {
        "external_id": "security-1",
        "customer_email": "user@example.com",
        "subject": "Test",
        "body": "Test",
    }


@pytest.mark.parametrize("path", ADMIN_GET_PATHS)
async def test_admin_get_requires_auth(client: AsyncClient, path: str) -> None:
    response = await client.get(path)
    assert response.status_code == 403


@pytest.mark.parametrize("path", ADMIN_GET_PATHS)
async def test_admin_get_rejects_wrong_key(
    client: AsyncClient,
    path: str,
) -> None:
    response = await client.get(
        path,
        headers={"X-Admin-API-Key": "wrong-key"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("path", ADMIN_POST_JSON_PATHS)
async def test_admin_post_json_requires_auth(
    client: AsyncClient,
    path: str,
) -> None:
    response = await client.post(
        path,
        json=review_body(),
    )
    assert response.status_code == 403


@pytest.mark.parametrize("path", ADMIN_POST_JSON_PATHS)
async def test_admin_post_json_rejects_wrong_key(
    client: AsyncClient,
    path: str,
) -> None:
    response = await client.post(
        path,
        json=review_body(),
        headers={"X-Admin-API-Key": "wrong-key"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("path", ADMIN_POST_NO_BODY_PATHS)
async def test_admin_post_no_body_requires_auth(
    client: AsyncClient,
    path: str,
) -> None:
    response = await client.post(path)
    assert response.status_code == 403


@pytest.mark.parametrize("path", ADMIN_POST_NO_BODY_PATHS)
async def test_admin_post_no_body_rejects_wrong_key(
    client: AsyncClient,
    path: str,
) -> None:
    response = await client.post(
        path,
        headers={"X-Admin-API-Key": "wrong-key"},
    )
    assert response.status_code == 403


async def test_webhook_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/webhooks/tickets",
        json=webhook_payload(),
    )
    assert response.status_code == 403


async def test_webhook_rejects_wrong_key(client: AsyncClient) -> None:
    response = await client.post(
        "/webhooks/tickets",
        json=webhook_payload(),
        headers={"X-Webhook-API-Key": "wrong-key"},
    )
    assert response.status_code == 403
