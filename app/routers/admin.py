"""Admin review endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query, status

from app.container import ServiceContainer
from app.core.security import verify_admin_key
from app.database.models import ReviewDecision, TicketStatus
from app.dependencies import get_container, get_routing_service, get_ticket_service
from app.schemas.ticket import ReviewAction, TicketOut
from app.services.routing_service import RoutingService
from app.services.ticket_service import TicketService

admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_key)],
)

TicketId = Annotated[int, Path(ge=1)]
TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]
RoutingServiceDep = Annotated[RoutingService, Depends(get_routing_service)]
ContainerDep = Annotated[ServiceContainer, Depends(get_container)]
ReviewStatusQuery = Annotated[TicketStatus, Query(alias="status")]


@admin_router.get("/reviews", response_model=list[TicketOut])
async def list_reviews(
    ticket_service: TicketServiceDep,
    status: ReviewStatusQuery = TicketStatus.MANUAL_REVIEW,
) -> list[TicketOut]:
    items, _ = await ticket_service.list(
        page=1,
        limit=100,
        status_filter=status,
    )
    return items


@admin_router.post("/reviews/{ticket_id}/approve", response_model=TicketOut)
async def approve_review(
    ticket_id: TicketId,
    action: ReviewAction,
    ticket_service: TicketServiceDep,
    routing_service: RoutingServiceDep,
) -> TicketOut:
    ticket = await ticket_service.apply_review(
        ticket_id=ticket_id,
        decision=ReviewDecision.APPROVED,
        reviewer_email=action.reviewer_email,
        comment=action.comment,
    )

    if ticket.ai_category and ticket.ai_urgency:
        assignee = await routing_service.resolve_assignee(
            category=ticket.ai_category,
            urgency=ticket.ai_urgency,
        )
        ticket = await ticket_service.assign(
            ticket_id=ticket.id,
            assignee=assignee,
            actor=action.reviewer_email,
        )

    return ticket


@admin_router.post("/reviews/{ticket_id}/reject", response_model=TicketOut)
async def reject_review(
    ticket_id: TicketId,
    action: ReviewAction,
    ticket_service: TicketServiceDep,
) -> TicketOut:
    return await ticket_service.apply_review(
        ticket_id=ticket_id,
        decision=ReviewDecision.REJECTED,
        reviewer_email=action.reviewer_email,
        comment=action.comment,
    )


@admin_router.post("/reviews/{ticket_id}/escalate", response_model=TicketOut)
async def escalate_review(
    ticket_id: TicketId,
    action: ReviewAction,
    ticket_service: TicketServiceDep,
) -> TicketOut:
    return await ticket_service.escalate(
        ticket_id=ticket_id,
        actor=action.reviewer_email,
        comment=action.comment,
    )


@admin_router.post("/tickets/{ticket_id}/resolve", response_model=TicketOut)
async def resolve_ticket(
    ticket_id: TicketId,
    ticket_service: TicketServiceDep,
) -> TicketOut:
    return await ticket_service.transition(
        ticket_id=ticket_id,
        target=TicketStatus.RESOLVED,
        actor="admin",
    )


@admin_router.post(
    "/tickets/{ticket_id}/reprocess",
    response_model=TicketOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_ticket(
    ticket_id: TicketId,
    background_tasks: BackgroundTasks,
    ticket_service: TicketServiceDep,
    container: ContainerDep,
) -> TicketOut:
    ticket = await ticket_service.reprocess(ticket_id)
    background_tasks.add_task(container.process_ticket_background, ticket.id)
    return ticket
