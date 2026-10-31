"""Application configuration using Pydantic Settings."""

from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "TicketPilot AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ticketpilot.db"

    # LLM
    LLM_API_KEY: str = ""
    LLM_API_URL: str = "https://api.openai.com/v1/chat/completions"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT: int = 10
    LLM_MAX_RETRIES: int = 2

    LLM_ENABLE_JSON_MODE: bool = True
    LLM_MAX_TOKENS: int = 300
    # Business Logic
    AI_CONFIDENCE_THRESHOLD: int = 80

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Security
    ADMIN_API_KEY: str = "dev-admin-key-change-in-production"
    WEBHOOK_API_KEY: str = "dev-webhook-key-change-in-production"


def build_settings(**overrides: Any) -> Settings:
    """
    Factory for settings.

    No module-level singleton.
    Settings are injected into TicketsPilotApplication explicitly.
    """
    return Settings(**overrides)
