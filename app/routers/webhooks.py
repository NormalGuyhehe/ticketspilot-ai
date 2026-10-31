"""Webhook ingestion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import ServiceContainer
from app.core.security import verify_webhook_key
from app.dependencies import get_container, get_db, get_ticket_service
from app.schemas.ticket import TicketCreate, TicketOut
from app.services.ticket_service import TicketService

webhooks_router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
    dependencies=[Depends(verify_webhook_key)],
)


@webhooks_router.post(
    "/tickets",
    response_model=TicketOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a new support ticket",
)
async def ingest_ticket(
    payload: TicketCreate,
    background_tasks: BackgroundTasks,
    ticket_service: TicketService = Depends(get_ticket_service),
    container: ServiceContainer = Depends(get_container),
    db: AsyncSession = Depends(get_db),
) -> TicketOut:
    """
    Idempotent webhook endpoint.

    - Validates payload via Pydantic
    - Checks duplicate by external_id
    - Saves ticket with status RECEIVED
    - Returns 202 Accepted
    - Triggers background AI processing only for newly created tickets
    """
    ticket, created = await ticket_service.create_or_get(payload)

    if created:
        # Commit before scheduling background task.
        # Background task must see a persisted ticket.
        await db.commit()
        background_tasks.add_task(container.process_ticket_background, ticket.id)

    return ticket
