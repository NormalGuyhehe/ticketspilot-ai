"""Pytest fixtures."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.app import TicketsPilotApplication
from app.config import Settings
from app.database.base import Base
from tests.fakes import FakeLLMClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_NAME="TicketPilot AI Test",
        APP_VERSION="0.0.1-test",
        DEBUG=False,
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        LLM_API_KEY="",
        LLM_API_URL="http://llm.test/v1/chat/completions",
        LLM_MODEL="test-model",
        LLM_TIMEOUT=1,
        LLM_MAX_RETRIES=1,
        AI_CONFIDENCE_THRESHOLD=80,
        CORS_ORIGINS=["*"],
        ADMIN_API_KEY="test-admin-key",
        WEBHOOK_API_KEY="test-webhook-key",
    )


@pytest.fixture
def llm_client() -> FakeLLMClient:
    return FakeLLMClient(
        response=None,
        enforce_threshold=True,
        threshold=80,
    )


@pytest_asyncio.fixture
async def application(
    settings: Settings,
    llm_client: FakeLLMClient,
):
    application = TicketsPilotApplication(
        settings=settings,
        llm_client=llm_client,
    )

    async with application.database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield application

    await application.container.aclose()
    await application.database.dispose()


@pytest_asyncio.fixture
async def client(application: TicketsPilotApplication):
    transport = ASGITransport(app=application.app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def webhook_headers() -> dict[str, str]:
    return {"X-Webhook-API-Key": "test-webhook-key"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-API-Key": "test-admin-key"}


@pytest_asyncio.fixture
async def db_session():
    """
    Isolated in-memory DB session for repository/service unit tests.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()
