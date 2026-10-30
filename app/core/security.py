"""Security utilities - API key authentication."""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import settings

admin_api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)
webhook_api_key_header = APIKeyHeader(name="X-Webhook-API-Key", auto_error=False)


async def verify_admin_key(api_key: str = Security(admin_api_key_header)) -> str:
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key",
        )
    return api_key


async def verify_webhook_key(api_key: str = Security(webhook_api_key_header)) -> str:
    if api_key != settings.WEBHOOK_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook API key",
        )
    return api_key
