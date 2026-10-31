"""Security utilities - API key authentication."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from app.config import Settings

admin_api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)
webhook_api_key_header = APIKeyHeader(name="X-Webhook-API-Key", auto_error=False)


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _constant_time_equals(value: str | None, expected: str) -> bool:
    if not value or not expected:
        return False
    return secrets.compare_digest(value, expected)


async def verify_admin_key(
    request: Request,
    api_key: str | None = Security(admin_api_key_header),
) -> str:
    settings = _get_settings(request)

    if not _constant_time_equals(api_key, settings.ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key",
        )

    return api_key


async def verify_webhook_key(
    request: Request,
    api_key: str | None = Security(webhook_api_key_header),
) -> str:
    settings = _get_settings(request)

    if not _constant_time_equals(api_key, settings.WEBHOOK_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook API key",
        )

    return api_key
