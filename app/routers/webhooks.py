"""Webhook ingestion endpoints."""
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.ticket import TicketCreate, TicketOut

router = APIRouter()


@router.post(
    "/tickets",
    response_model=TicketOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a new support ticket",
    description="Accepts ticket from external system. Returns 202 immediately, processes async.",
)
async def ingest_ticket(
    payload: TicketCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Idempotent webhook endpoint.
    - Validates payload via Pydantic
    - Checks for duplicate by external_id
    - Saves with status=RECEIVED
    - Triggers background AI classification
    """
    # TODO: Implement
    raise NotImplementedError
