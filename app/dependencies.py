"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.container import ServiceContainer
from app.database.session import Database
from app.services.metrics_service import MetricsService
from app.services.routing_service import RoutingService
from app.services.ticket_processing_service import TicketProcessingService
from app.services.ticket_service import TicketService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


async def get_db(
    database: Database = Depends(get_database),
) -> AsyncGenerator[AsyncSession, None]:
    async for session in database.session():
        yield session


def get_ticket_service(
    db: AsyncSession = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> TicketService:
    return container.make_ticket_service(db)


def get_routing_service(
    db: AsyncSession = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> RoutingService:
    return container.make_routing_service(db)


def get_metrics_service(
    db: AsyncSession = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> MetricsService:
    return container.make_metrics_service(db)


def get_ticket_processing_service(
    db: AsyncSession = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> TicketProcessingService:
    return container.make_processing_service(db)
