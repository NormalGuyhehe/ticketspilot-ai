"""Exhaustive state machine transition tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidStateTransitionError
from app.database.models import Ticket, TicketStatus
from app.repositories.ticket_repository import TicketRepository
from app.services.ticket_service import ALLOWED_TRANSITIONS, TicketService

ALL_STATUSES = list(TicketStatus)


async def _make_ticket(db: AsyncSession, status: TicketStatus) -> Ticket:
    ticket = Ticket(
        external_id=f"sm-{status.value}",
        customer_email="user@example.com",
        subject="State machine test",
        body="State machine body",
        status=status,
    )

    db.add(ticket)
    await db.flush()
    await db.refresh(ticket)

    return ticket


@pytest.mark.parametrize("current", ALL_STATUSES)
@pytest.mark.parametrize("target", ALL_STATUSES)
async def test_state_machine_matrix(
    db_session: AsyncSession,
    current: TicketStatus,
    target: TicketStatus,
) -> None:
    """
    Verify every possible transition against ALLOWED_TRANSITIONS.

    This is a hard contract test for the ticket lifecycle.
    """
    ticket = await _make_ticket(db_session, current)
    service = TicketService(TicketRepository(db_session))

    allowed = target in ALLOWED_TRANSITIONS.get(current, set())

    if allowed:
        updated = await service.transition(
            ticket.id,
            target,
            actor="test",
        )

        assert updated.status == target

        if target == TicketStatus.RESOLVED:
            assert updated.resolved_at is not None
    else:
        with pytest.raises(InvalidStateTransitionError):
            await service.transition(
                ticket.id,
                target,
                actor="test",
            )
