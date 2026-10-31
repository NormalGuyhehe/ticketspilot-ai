"""OpenAPI contract tests."""

from __future__ import annotations

from httpx import AsyncClient

from app.schemas.ai import AIClassificationResult


async def test_openapi_contains_expected_paths_and_methods(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()
    paths = schema["paths"]

    assert paths["/health"]["get"]["responses"]["200"]
    assert paths["/webhooks/tickets"]["post"]["responses"]["202"]

    assert paths["/tickets"]["get"]["responses"]["200"]
    assert paths["/tickets/{ticket_id}"]["get"]["responses"]["200"]
    assert paths["/tickets/{ticket_id}/history"]["get"]["responses"]["200"]

    assert paths["/admin/reviews"]["get"]["responses"]["200"]
    assert paths["/admin/reviews/{ticket_id}/approve"]["post"]["responses"]["200"]
    assert paths["/admin/reviews/{ticket_id}/reject"]["post"]["responses"]["200"]
    assert paths["/admin/reviews/{ticket_id}/escalate"]["post"]["responses"]["200"]
    assert paths["/admin/tickets/{ticket_id}/resolve"]["post"]["responses"]["200"]

    assert paths["/metrics/summary"]["get"]["responses"]["200"]
    assert paths["/metrics/accuracy"]["get"]["responses"]["200"]
    assert paths["/metrics/processing-time"]["get"]["responses"]["200"]


async def test_openapi_ticket_create_schema_required_fields(
    client: AsyncClient,
) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()
    components = schema["components"]["schemas"]

    assert "TicketCreate" in components

    required = set(components["TicketCreate"]["required"])

    assert {
        "external_id",
        "customer_email",
        "subject",
        "body",
    }.issubset(required)


def test_ai_classification_schema_bounds_direct_pydantic() -> None:
    """
    AIClassificationResult is an internal AI DTO.

    It must be validated by Pydantic itself, not necessarily exposed via OpenAPI.
    """
    schema = AIClassificationResult.model_json_schema()
    properties = schema["properties"]

    assert properties["confidence"]["minimum"] == 0
    assert properties["confidence"]["maximum"] == 100
    assert properties["summary"]["maxLength"] == 200

    required = set(schema["required"])

    assert required == {
        "category",
        "urgency",
        "summary",
        "confidence",
    }


async def test_internal_ai_schema_is_not_leaked_to_public_openapi(
    client: AsyncClient,
) -> None:
    """
    Guard architectural boundary.

    Internal AI response schema should not become part of public API contract
    unless explicitly exposed through a route.
    """
    response = await client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()
    components = schema.get("components", {}).get("schemas", {})

    assert "AIClassificationResult" not in components
