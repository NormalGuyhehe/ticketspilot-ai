"""Async database session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import Settings


class Database:
    """
    Database wrapper.

    Owns engine and session factory.
    Provides request-scoped session dependency and standalone session scope
    for background tasks.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        engine_kwargs: dict[str, Any] = {
            "echo": settings.DEBUG,
            "future": True,
            "pool_pre_ping": True,
        }

        # Required for in-memory SQLite in tests.
        if (
            settings.DATABASE_URL.startswith("sqlite")
            and ":memory:" in settings.DATABASE_URL
        ):
            engine_kwargs["poolclass"] = StaticPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}

        self._engine = create_async_engine(
            settings.DATABASE_URL,
            **engine_kwargs,
        )

        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @property
    def engine(self):
        return self._engine

    async def dispose(self) -> None:
        await self._engine.dispose()

    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI-friendly async generator dependency.

        Usage:
            async for session in database.session():
                yield session
        """
        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def session_scope(self):
        """
        Standalone session scope for background tasks, scripts, tests.
        """
        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
