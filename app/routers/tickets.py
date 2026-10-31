"""Ticket query endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.core.security import verify_admin_key
from app.database.models import TicketStatus
from app.dependencies import get_ticket_service
from app.schemas.ticket import TicketHistoryOut, TicketListResponse, TicketOut
from app.services.ticket_service import TicketService

tickets_router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
    dependencies=[Depends(verify_admin_key)],
)

TicketId = Annotated[int, Path(ge=1)]
TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]

PageQuery = Annotated[int, Query(ge=1)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
StatusQuery = Annotated[TicketStatus | None, Query(alias="status")]


@tickets_router.get("", response_model=TicketListResponse)
async def list_tickets(
    ticket_service: TicketServiceDep,
    page: PageQuery = 1,
    limit: LimitQuery = 20,
    status: StatusQuery = None,
) -> TicketListResponse:
    items, total = await ticket_service.list(
        page=page,
        limit=limit,
        status_filter=status,
    )

    return TicketListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
    )


@tickets_router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(
    ticket_id: TicketId,
    ticket_service: TicketServiceDep,
) -> TicketOut:
    return await ticket_service.get(ticket_id)


@tickets_router.get("/{ticket_id}/history", response_model=list[TicketHistoryOut])
async def get_ticket_history(
    ticket_id: TicketId,
    ticket_service: TicketServiceDep,
) -> list[TicketHistoryOut]:
    history = await ticket_service.get_history(ticket_id)
    return [TicketHistoryOut.model_validate(item) for item in history]
