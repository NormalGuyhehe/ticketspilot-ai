"""OpenAPI contract tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_openapi_json_contains_core_endpoints(client: AsyncClient):
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()

    paths = schema["paths"]

    assert "/webhooks/tickets" in paths
    assert "/tickets" in paths
    assert "/tickets/{ticket_id}" in paths
    assert "/admin/reviews" in paths
    assert "/admin/reviews/{ticket_id}/approve" in paths
    assert "/metrics/summary" in paths
    assert "/health" in paths


async def test_swagger_docs_available(client: AsyncClient):
    response = await client.get("/docs")
    assert response.status_code == 200
