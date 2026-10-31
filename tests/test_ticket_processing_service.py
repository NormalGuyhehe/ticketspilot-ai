"""Ticket processing orchestrator tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from app.database.models import Ticket, TicketStatus
from app.services.ticket_processing_service import TicketProcessingService
from tests.fakes import FakeLLMClient
from tests.helpers import confident_ai, low_ai


def make_ticket(status: TicketStatus = TicketStatus.RECEIVED) -> Ticket:
    return Ticket(
        id=1,
        external_id="process-1",
        customer_email="user@example.com",
        subject="Login issue",
        body="Cannot login",
        status=status,
    )


async def test_process_skips_if_ticket_not_received():
    ticket = make_ticket(TicketStatus.PROCESSING)

    ticket_service = AsyncMock()
    ticket_service.get.return_value = ticket

    service = TicketProcessingService(
        ticket_service=ticket_service,
        routing_service=AsyncMock(),
        llm_client=FakeLLMClient(response=confident_ai()),
    )

    result = await service.process(1)

    assert result is ticket
    ticket_service.transition.assert_not_called()


async def test_high_confidence_routes_automatically():
    ticket = make_ticket()

    ticket_service = AsyncMock()
    ticket_service.get.return_value = ticket
    ticket_service.transition.return_value = ticket
    ticket_service.attach_ai_result.return_value = ticket
    ticket_service.mark_auto_routed.return_value = ticket

    routing_service = AsyncMock()
    routing_service.resolve_assignee.return_value = "tech-support@example.com"

    llm_client = FakeLLMClient(response=confident_ai())

    service = TicketProcessingService(
        ticket_service=ticket_service,
        routing_service=routing_service,
        llm_client=llm_client,
    )

    await service.process(1)

    assert llm_client.calls == [("Login issue", "Cannot login")]

    ticket_service.transition.assert_any_call(
        1,
        TicketStatus.PROCESSING,
        actor="background-worker",
    )

    ticket_service.attach_ai_result.assert_awaited_once()
    routing_service.resolve_assignee.assert_awaited_once_with(
        category="Technical",
        urgency="High",
    )
    ticket_service.mark_auto_routed.assert_awaited_once_with(
        1,
        assignee="tech-support@example.com",
        actor="background-worker",
    )


async def test_low_confidence_routes_to_manual_review():
    ticket = make_ticket()

    ticket_service = AsyncMock()
    ticket_service.get.return_value = ticket
    ticket_service.transition.return_value = ticket
    ticket_service.attach_ai_result.return_value = ticket

    routing_service = AsyncMock()
    llm_client = FakeLLMClient(response=low_ai())

    service = TicketProcessingService(
        ticket_service=ticket_service,
        routing_service=routing_service,
        llm_client=llm_client,
    )

    await service.process(1)

    transitions = [call.args[1] for call in ticket_service.transition.await_args_list]

    assert TicketStatus.PROCESSING in transitions
    assert TicketStatus.MANUAL_REVIEW in transitions

    routing_service.resolve_assignee.assert_not_called()
    ticket_service.mark_auto_routed.assert_not_called()


async def test_llm_unavailable_routes_to_manual_review_with_marker():
    ticket = make_ticket()

    ticket_service = AsyncMock()
    ticket_service.get.return_value = ticket
    ticket_service.transition.return_value = ticket
    ticket_service.set_ai_summary.return_value = ticket

    routing_service = AsyncMock()
    llm_client = FakeLLMClient(response=None)

    service = TicketProcessingService(
        ticket_service=ticket_service,
        routing_service=routing_service,
        llm_client=llm_client,
    )

    await service.process(1)

    ticket_service.transition.assert_any_call(
        1,
        TicketStatus.MANUAL_REVIEW,
        actor="background-worker",
    )
    ticket_service.set_ai_summary.assert_awaited_once_with(
        1,
        "AI_UNAVAILABLE",
    )
    routing_service.resolve_assignee.assert_not_called()
