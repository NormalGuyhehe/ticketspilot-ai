"""Application lifespan tests."""

from __future__ import annotations

from sqlalchemy import text

from app.app import TicketsPilotApplication
from app.config import Settings
from app.database.base import Base
from tests.fakes import FakeLLMClient


async def test_startup_checks_pass_with_valid_database(
    application: TicketsPilotApplication,
):
    await application._startup_checks()


async def test_lifespan_starts_and_stops_cleanly(
    settings: Settings,
):
    llm_client = FakeLLMClient(response=None)
    application = TicketsPilotApplication(
        settings=settings,
        llm_client=llm_client,
    )

    async with application.database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with application.app.router.lifespan_context(application.app):
        async with application.database.session_scope() as db:
            result = await db.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
