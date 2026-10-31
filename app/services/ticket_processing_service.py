"""Background processing orchestrator."""

from __future__ import annotations

import logging
import re

from app.clients.llm_client import LLMClient
from app.database.models import Ticket, TicketStatus
from app.services.routing_service import RoutingService
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)

# Deterministic patterns that force human review regardless of AI confidence
AMBIGUOUS_PATTERNS = (
    r"^help$",
    r"^urgent$",
    r"see attached",
    r"it doesn't work",
    r"something is wrong",
    r"urgent help",
)

SENSITIVE_PATTERNS = (
    r"gdpr",
    r"legal",
    r"lawsuit",
    r"security",
    r"compromised",
    r"production outage",
    r"charge twice",
    r"duplicate charge",
)


class TicketProcessingService:
    """
    Orchestrates:
    - state transition to PROCESSING
    - LLM classification
    - automatic routing or manual review
    """

    def __init__(
        self,
        ticket_service: TicketService,
        routing_service: RoutingService,
        llm_client: LLMClient,
    ) -> None:
        self._ticket_service = ticket_service
        self._routing_service = routing_service
        self._llm_client = llm_client

    @staticmethod
    def _should_force_manual_review(ticket: Ticket, ai_confidence: int | None) -> bool:
        """
        Deterministic guard that forces MANUAL_REVIEW for:
        - ambiguous tickets (short, no context)
        - sensitive tickets (GDPR, legal, production outage)
        - low confidence from AI

        This runs AFTER AI classification to override auto-routing
        when the ticket is clearly unsafe for automatic handling.
        """
        text = f"{ticket.subject} {ticket.body}".lower()

        # Short body without actionable context
        if len(ticket.body.strip()) < 20:
            return True

        # Ambiguous patterns
        if any(
            re.search(pattern, text, flags=re.IGNORECASE)
            for pattern in AMBIGUOUS_PATTERNS
        ):
            return True

        # Sensitive patterns
        if any(
            re.search(pattern, text, flags=re.IGNORECASE)
            for pattern in SENSITIVE_PATTERNS
        ):
            return True

        # Low confidence
        if ai_confidence is not None and ai_confidence < 80:
            return True

        return False

    async def process(self, ticket_id: int) -> Ticket:
        ticket = await self._ticket_service.get(ticket_id)

        if ticket.status != TicketStatus.RECEIVED:
            logger.warning(
                "Ticket %d already in status %s, skipping processing",
                ticket_id,
                ticket.status,
            )
            return ticket

        await self._ticket_service.transition(
            ticket_id,
            TicketStatus.PROCESSING,
            actor="background-worker",
        )

        ai_result = await self._llm_client.classify(
            subject=ticket.subject,
            body=ticket.body,
        )

        if ai_result is None:
            await self._ticket_service.transition(
                ticket_id,
                TicketStatus.MANUAL_REVIEW,
                actor="background-worker",
            )
            await self._ticket_service.set_ai_summary(
                ticket_id,
                "AI_UNAVAILABLE",
            )
            logger.info("Ticket %d routed to MANUAL_REVIEW: LLM unavailable", ticket_id)
            return await self._ticket_service.get(ticket_id)

        await self._ticket_service.attach_ai_result(ticket_id, ai_result)

        # Deterministic guard: force MANUAL_REVIEW for ambiguous/sensitive tickets
        if self._should_force_manual_review(ticket, ai_result.confidence):
            await self._ticket_service.transition(
                ticket_id,
                TicketStatus.MANUAL_REVIEW,
                actor="background-worker",
            )
            logger.info(
                "Ticket %d routed to MANUAL_REVIEW: deterministic guard", ticket_id
            )
        else:
            assignee = await self._routing_service.resolve_assignee(
                category=ai_result.category,
                urgency=ai_result.urgency,
            )
            await self._ticket_service.mark_auto_routed(
                ticket_id,
                assignee=assignee,
                actor="background-worker",
            )
            logger.info("Ticket %d routed to AUTO_ROUTED: %s", ticket_id, assignee)

        return await self._ticket_service.get(ticket_id)
