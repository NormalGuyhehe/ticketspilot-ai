"""FastAPI application assembly."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.clients.llm_client import LLMClient
from app.config import Settings
from app.container import ServiceContainer
from app.database.session import Database

from .routers import take_main_router

logger = logging.getLogger(__name__)


class TicketsPilotApplication:
    """
    Application builder.

    Either fully constructs, or fails fast.
    No lazy global singletons.
    """

    def __init__(
        self,
        settings: Settings,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.database = Database(settings)
        self.container = ServiceContainer(
            settings=settings,
            database=self.database,
            llm_client=llm_client,
        )

        self.app = FastAPI(
            title=settings.APP_NAME,
            version=settings.APP_VERSION,
            description="AI-powered support ticket automation system",
            docs_url="/docs",
            redoc_url="/redoc",
            lifespan=self._lifespan,
        )

        self._register_state()
        self._create_middlewares()
        self._connect_routers()

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        logger.info("TicketPilot AI startup")

        await self._startup_checks()

        try:
            yield
        finally:
            logger.info("TicketPilot AI shutdown")
            await self.container.aclose()
            await self.database.dispose()

    async def _startup_checks(self) -> None:
        """
        Fail-fast checks.

        If DB is unreachable, application does not start.
        """
        async with self.database.session_scope() as session:
            await session.execute(text("SELECT 1"))

        if not self.settings.LLM_API_KEY and self.settings.LLM_API_URL.startswith(
            "https://"
        ):
            logger.warning(
                "LLM_API_KEY is empty. Remote LLM calls will fail and tickets "
                "will be routed to MANUAL_REVIEW."
            )

    def _register_state(self) -> None:
        self.app.state.settings = self.settings
        self.app.state.database = self.database
        self.app.state.container = self.container

    def _create_middlewares(self) -> None:
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _connect_routers(self) -> None:
        self.app.include_router(take_main_router())
