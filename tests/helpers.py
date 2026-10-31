"""Shared test helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from app.app import TicketsPilotApplication
from app.database.models import Ticket, TicketStatus
from app.schemas.ai import AIClassificationResult
from app.schemas.ticket import TicketCreate


async def seed_ticket(
    application: TicketsPilotApplication,
    external_id: str,
    **kwargs,
) -> int:
    """
    Directly seed ticket into application database.

    Bypasses state machine intentionally for query/metrics tests.
    For lifecycle tests use service-level helpers or API.
    """
    created_at = kwargs.pop("created_at", None) or datetime.now(UTC)

    data = {
        "external_id": external_id,
        "customer_email": kwargs.pop("customer_email", "user@example.com"),
        "subject": kwargs.pop("subject", "Test subject"),
        "body": kwargs.pop("body", "Test body"),
        "status": kwargs.pop("status", TicketStatus.RECEIVED),
        "created_at": created_at,
    }
    data.update(kwargs)

    async with application.database.session_scope() as db:
        ticket = Ticket(**data)
        db.add(ticket)
        await db.flush()
        await db.refresh(ticket)
        return ticket.id


async def create_ticket_with_history(
    application: TicketsPilotApplication,
    external_id: str,
) -> int:
    """
    Create ticket through real service so history is recorded.
    """
    async with application.database.session_scope() as db:
        service = application.container.make_ticket_service(db)
        ticket = await service.create(
            TicketCreate(
                external_id=external_id,
                customer_email="user@example.com",
                subject="History test",
                body="History test body",
            )
        )
        await service.transition(
            ticket.id,
            TicketStatus.PROCESSING,
            actor="test",
        )
        return ticket.id


def confident_ai(
    *,
    category: str = "Technical",
    urgency: str = "High",
    summary: str = "Login failure",
    confidence: int = 92,
) -> AIClassificationResult:
    return AIClassificationResult(
        category=category,
        urgency=urgency,
        summary=summary,
        confidence=confidence,
        requires_human_review=False,
        missing_context=[],
    )


def low_ai(
    *,
    category: str = "General",
    urgency: str = "Low",
    summary: str = "Ambiguous request",
    confidence: int = 50,
) -> AIClassificationResult:
    return AIClassificationResult(
        category=category,
        urgency=urgency,
        summary=summary,
        confidence=confidence,
        requires_human_review=False,
        missing_context=["need more context"],
    )
