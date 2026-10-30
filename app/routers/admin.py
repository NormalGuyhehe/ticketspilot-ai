"""Admin review endpoints."""
from fastapi import APIRouter, Depends

from app.schemas.ticket import TicketOut, ReviewAction

router = APIRouter()


@router.get("/reviews", response_model=list[TicketOut])
async def list_reviews():
    # TODO: Implement
    raise NotImplementedError


@router.post("/reviews/{ticket_id}/approve", response_model=TicketOut)
async def approve_review(ticket_id: int, action: ReviewAction):
    # TODO: Implement
    raise NotImplementedError


@router.post("/reviews/{ticket_id}/reject", response_model=TicketOut)
async def reject_review(ticket_id: int, action: ReviewAction):
    # TODO: Implement
    raise NotImplementedError


@router.post("/reviews/{ticket_id}/escalate", response_model=TicketOut)
async def escalate_review(ticket_id: int, action: ReviewAction):
    # TODO: Implement
    raise NotImplementedError


@router.post("/tickets/{ticket_id}/resolve", response_model=TicketOut)
async def resolve_ticket(ticket_id: int):
    # TODO: Implement
    raise NotImplementedError
