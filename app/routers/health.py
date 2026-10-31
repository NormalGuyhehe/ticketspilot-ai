"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import Settings

health_router = APIRouter(tags=["System"])


@health_router.get("/health")
async def health_check(request: Request) -> dict:
    settings: Settings = request.app.state.settings

    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
