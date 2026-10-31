"""Ticket service business logic tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidStateTransitionError,
    TicketNotFoundError,
)
from app.database.models import ReviewDecision, TicketStatus
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ai import AIClassificationResult
from app.schemas.ticket import TicketCreate
from app.services.ticket_service import TicketService


@pytest.fixture
def payload() -> TicketCreate:
    return TicketCreate(
        external_id="service-1",
        customer_email="user@example.com",
        subject="Cannot login",
        body="I cannot login to my account.",
    )


@pytest.fixture
def service(db_session: AsyncSession) -> TicketService:
    return TicketService(TicketRepository(db_session))


async def test_create_sets_received_status_and_history(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)

    assert ticket.status == TicketStatus.RECEIVED

    history = await service.get_history(ticket.id)
    assert len(history) == 1
    assert history[0].action == "CREATED"
    assert history[0].new_value == TicketStatus.RECEIVED.value
    assert history[0].actor == "webhook"


async def test_get_missing_ticket_raises(
    service: TicketService,
):
    with pytest.raises(TicketNotFoundError):
        await service.get(99999)


async def test_create_or_get_is_idempotent(
    service: TicketService,
    payload: TicketCreate,
    db_session: AsyncSession,
):
    first, created_first = await service.create_or_get(payload)
    first_id = first.id
    await db_session.commit()

    second, created_second = await service.create_or_get(payload)

    assert created_first is True
    assert created_second is False
    assert second.id == first_id


async def test_valid_transition_received_to_processing(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)

    updated = await service.transition(
        ticket.id,
        TicketStatus.PROCESSING,
        actor="worker",
    )

    assert updated.status == TicketStatus.PROCESSING

    history = await service.get_history(ticket.id)
    assert history[-1].action == "STATUS_CHANGED"
    assert history[-1].old_value == TicketStatus.RECEIVED.value
    assert history[-1].new_value == TicketStatus.PROCESSING.value
    assert history[-1].actor == "worker"


async def test_invalid_transition_raises(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)

    with pytest.raises(InvalidStateTransitionError):
        await service.transition(ticket.id, TicketStatus.AUTO_ROUTED)


async def test_resolved_is_terminal(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)

    await service.transition(ticket.id, TicketStatus.PROCESSING)
    await service.transition(ticket.id, TicketStatus.AUTO_ROUTED)
    resolved = await service.transition(ticket.id, TicketStatus.RESOLVED)

    assert resolved.status == TicketStatus.RESOLVED
    assert resolved.resolved_at is not None

    with pytest.raises(InvalidStateTransitionError):
        await service.transition(ticket.id, TicketStatus.PROCESSING)


async def test_apply_review_approve(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)
    await service.transition(ticket.id, TicketStatus.PROCESSING)
    await service.transition(ticket.id, TicketStatus.MANUAL_REVIEW)

    reviewed = await service.apply_review(
        ticket.id,
        ReviewDecision.APPROVED,
        reviewer_email="operator@example.com",
        comment="Looks correct",
    )

    assert reviewed.status == TicketStatus.APPROVED
    assert reviewed.reviewed_by == "operator@example.com"
    assert reviewed.review_decision == ReviewDecision.APPROVED
    assert reviewed.review_comment == "Looks correct"

    history = await service.get_history(ticket.id)
    assert history[-1].action == "REVIEWED"
    assert history[-1].new_value == TicketStatus.APPROVED.value


async def test_apply_review_reject(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)
    await service.transition(ticket.id, TicketStatus.PROCESSING)
    await service.transition(ticket.id, TicketStatus.MANUAL_REVIEW)

    reviewed = await service.apply_review(
        ticket.id,
        ReviewDecision.REJECTED,
        reviewer_email="operator@example.com",
        comment="Wrong category",
    )

    assert reviewed.status == TicketStatus.REJECTED
    assert reviewed.review_decision == ReviewDecision.REJECTED


async def test_rejected_can_return_to_manual_review(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)
    await service.transition(ticket.id, TicketStatus.PROCESSING)
    await service.transition(ticket.id, TicketStatus.MANUAL_REVIEW)
    await service.apply_review(
        ticket.id,
        ReviewDecision.REJECTED,
        reviewer_email="operator@example.com",
        comment="Retry",
    )

    re_reviewed = await service.transition(
        ticket.id,
        TicketStatus.MANUAL_REVIEW,
        actor="operator@example.com",
    )

    assert re_reviewed.status == TicketStatus.MANUAL_REVIEW


async def test_escalate_from_manual_review(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)
    await service.transition(ticket.id, TicketStatus.PROCESSING)
    await service.transition(ticket.id, TicketStatus.MANUAL_REVIEW)

    escalated = await service.escalate(
        ticket.id,
        actor="lead@example.com",
        comment="Needs L2",
    )

    assert escalated.status == TicketStatus.ESCALATED
    assert escalated.reviewed_by == "lead@example.com"
    assert escalated.review_comment == "Needs L2"


async def test_attach_ai_result(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)
    await service.transition(ticket.id, TicketStatus.PROCESSING)

    ai = AIClassificationResult(
        category="Billing",
        urgency="Medium",
        summary="Invoice question",
        confidence=88,
        requires_human_review=False,
        missing_context=[],
    )

    updated = await service.attach_ai_result(ticket.id, ai)

    assert updated.ai_category == "Billing"
    assert updated.ai_urgency == "Medium"
    assert updated.ai_summary == "Invoice question"
    assert updated.ai_confidence == 88
    assert updated.ai_raw_response is not None
    assert updated.ai_raw_response["category"] == "Billing"


async def test_mark_auto_routed(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)
    await service.transition(ticket.id, TicketStatus.PROCESSING)

    routed = await service.mark_auto_routed(
        ticket.id,
        assignee="billing-team@example.com",
        actor="worker",
    )

    assert routed.status == TicketStatus.AUTO_ROUTED
    assert routed.assigned_to == "billing-team@example.com"

    history = await service.get_history(ticket.id)
    assert history[-1].action == "AUTO_ROUTED"


async def test_reprocess_allowed_only_for_ai_failed_tickets(
    service: TicketService,
    payload: TicketCreate,
):
    ticket = await service.create(payload)
    await service.transition(ticket.id, TicketStatus.PROCESSING)
    await service.transition(ticket.id, TicketStatus.MANUAL_REVIEW)
    await service.set_ai_summary(ticket.id, "AI_UNAVAILABLE")

    reprocessed = await service.reprocess(ticket.id)

    assert reprocessed.status == TicketStatus.RECEIVED
    assert reprocessed.ai_summary is None
    assert reprocessed.ai_category is None


async def test_reprocess_rejected_when_ai_classification_present(
    service: TicketService,
    payload: TicketCreate,
):
    from app.core.exceptions import ReprocessNotAllowedError

    ticket = await service.create(payload)
    await service.transition(ticket.id, TicketStatus.PROCESSING)
    await service.transition(ticket.id, TicketStatus.MANUAL_REVIEW)
    await service.attach_ai_result(
        ticket.id,
        AIClassificationResult(
            category="Billing",
            urgency="High",
            summary="Real classification",
            confidence=70,
            requires_human_review=True,
            missing_context=[],
        ),
    )

    with pytest.raises(ReprocessNotAllowedError):
        await service.reprocess(ticket.id)
