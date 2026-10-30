"""Ticket query endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.ticket import TicketListResponse, TicketOut

router = APIRouter()


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    page: int = 1,
    limit: int = 20,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    # TODO: Implement
    raise NotImplementedError


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)):
    # TODO: Implement
    raise NotImplementedError


@router.get("/{ticket_id}/history")
async def get_ticket_history(ticket_id: int, db: AsyncSession = Depends(get_db)):
    # TODO: Implement
    raise NotImplementedError
