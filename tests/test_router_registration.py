"""Router wiring tests."""

from __future__ import annotations

from fastapi import FastAPI

from app.routers import take_main_router
from app.routers.admin import admin_router
from app.routers.health import health_router
from app.routers.metrics import metrics_router
from app.routers.tickets import tickets_router
from app.routers.webhooks import webhooks_router


def test_domain_routers_are_not_empty() -> None:
    """
    Guard against the classic bug:
    endpoints are registered on a local `router`,
    but the module exports an empty `xxx_router`.
    """
    assert admin_router.routes, "admin_router is empty. Check @admin_router decorators."
    assert tickets_router.routes, (
        "tickets_router is empty. Check @tickets_router decorators."
    )
    assert webhooks_router.routes, (
        "webhooks_router is empty. Check @webhooks_router decorators."
    )
    assert metrics_router.routes, (
        "metrics_router is empty. Check @metrics_router decorators."
    )
    assert health_router.routes, (
        "health_router is empty. Check @health_router decorators."
    )


def test_main_router_registers_expected_paths() -> None:
    """
    Verify that main_router correctly aggregates all sub-routers with their prefixes.

    Strategy:
    1. Create a temporary FastAPI app.
    2. Include main_router into it.
    3. Inspect generated OpenAPI paths.
    """
    temp_app = FastAPI()
    temp_app.include_router(take_main_router())

    schema = temp_app.openapi()
    actual_paths = set(schema.get("paths", {}).keys())

    expected_paths = {
        "/health",
        "/webhooks/tickets",
        "/tickets",
        "/tickets/{ticket_id}",
        "/tickets/{ticket_id}/history",
        "/admin/reviews",
        "/admin/reviews/{ticket_id}/approve",
        "/admin/reviews/{ticket_id}/reject",
        "/admin/reviews/{ticket_id}/escalate",
        "/admin/tickets/{ticket_id}/resolve",
        "/metrics/summary",
        "/metrics/accuracy",
        "/metrics/processing-time",
    }

    missing = expected_paths - actual_paths
    unexpected = actual_paths - expected_paths

    assert not missing, (
        f"Missing required routes: {missing}. "
        f"Found routes: {sorted(actual_paths)}. "
        f"Unexpected routes: {sorted(unexpected)}."
    )
