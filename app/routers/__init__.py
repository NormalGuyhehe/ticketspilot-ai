"""Main router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from .admin import admin_router
from .health import health_router
from .metrics import metrics_router
from .tickets import tickets_router
from .webhooks import webhooks_router

main_router = APIRouter()

main_router.include_router(admin_router)
main_router.include_router(metrics_router)
main_router.include_router(tickets_router)
main_router.include_router(webhooks_router)
main_router.include_router(health_router)


def take_main_router() -> APIRouter:
    return main_router


__all__ = ["take_main_router"]
