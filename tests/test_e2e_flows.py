"""Background processing isolation tests."""

from __future__ import annotations

from app.database.models import Ticket, TicketStatus
from app.schemas.ticket import TicketCreate
from tests.helpers import confident_ai, seed_ticket


async def test_background_uses_independent_session_and_processes_committed_ticket(
    application,
    llm_client,
) -> None:
    """
    Ticket is created and committed in one session.

    Background processing must see it in a separate session.
    """
    llm_client.response = confident_ai()

    async with application.database.session_scope() as db:
        service = application.container.make_ticket_service(db)

        ticket = await service.create(
            TicketCreate(
                external_id="bg-independent-1",
                customer_email="user@example.com",
                subject="Login issue",
                body="Cannot login to account",
            )
        )

        ticket_id = ticket.id

    await application.container.process_ticket_background(ticket_id)

    async with application.database.session_scope() as db:
        stored = await db.get(Ticket, ticket_id)

        assert stored is not None
        assert stored.status == TicketStatus.AUTO_ROUTED
        assert stored.ai_category == "Technical"
        assert stored.ai_urgency == "High"
        assert stored.assigned_to == "tech-support@example.com"


async def test_background_skips_ticket_not_in_received_state(
    application,
    llm_client,
) -> None:
    """
    If ticket is already PROCESSING, background task must not touch it.
    """
    llm_client.response = confident_ai()

    ticket_id = await seed_ticket(
        application,
        "bg-skip-1",
        status=TicketStatus.PROCESSING,
    )

    await application.container.process_ticket_background(ticket_id)

    async with application.database.session_scope() as db:
        stored = await db.get(Ticket, ticket_id)

        assert stored is not None
        assert stored.status == TicketStatus.PROCESSING
        assert stored.ai_category is None
        assert stored.assigned_to is None
