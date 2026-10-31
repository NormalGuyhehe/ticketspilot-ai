"""Ticket business logic - state machine, history, CRUD orchestration."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.exceptions import (
    DuplicateTicketError,
    InvalidStateTransitionError,
    ReprocessNotAllowedError,
    TicketNotFoundError,
)
from app.database.models import (
    ReviewDecision,
    Ticket,
    TicketHistory,
    TicketStatus,
)
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ai import AIClassificationResult
from app.schemas.ticket import TicketCreate

logger = logging.getLogger(__name__)

REPROCESSABLE_AI_MARKERS = {"AI_UNAVAILABLE", "SYSTEM_ERROR", "PARSE_ERROR"}

ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.RECEIVED: {TicketStatus.PROCESSING},
    TicketStatus.PROCESSING: {
        TicketStatus.AUTO_ROUTED,
        TicketStatus.MANUAL_REVIEW,
    },
    TicketStatus.MANUAL_REVIEW: {
        TicketStatus.APPROVED,
        TicketStatus.REJECTED,
        TicketStatus.ESCALATED,
        TicketStatus.RECEIVED,  # retry after AI failure
    },
    TicketStatus.AUTO_ROUTED: {
        TicketStatus.RESOLVED,
        TicketStatus.ESCALATED,
    },
    TicketStatus.APPROVED: {TicketStatus.RESOLVED},
    TicketStatus.ESCALATED: {TicketStatus.RESOLVED},
    TicketStatus.RESOLVED: set(),
    TicketStatus.REJECTED: {TicketStatus.MANUAL_REVIEW},
}


class TicketService:
    """
    Business logic for ticket lifecycle.

    Does not know HTTP.
    Does not know SQLAlchemy directly.
    Works through TicketRepository.
    """

    def __init__(self, repo: TicketRepository) -> None:
        self._repo = repo

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _assert_transition(current: TicketStatus, target: TicketStatus) -> None:
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidStateTransitionError(current.value, target.value)

    async def _record_history(
        self,
        ticket_id: int,
        action: str,
        old_value: str | None,
        new_value: str | None,
        actor: str = "system",
    ) -> None:
        await self._repo.add_history(
            TicketHistory(
                ticket_id=ticket_id,
                action=action,
                old_value=old_value,
                new_value=new_value,
                actor=actor,
            )
        )

    async def create(self, payload: TicketCreate) -> Ticket:
        ticket = Ticket(
            external_id=payload.external_id,
            customer_email=payload.customer_email,
            subject=payload.subject,
            body=payload.body,
            status=TicketStatus.RECEIVED,
        )

        ticket = await self._repo.create(ticket)

        await self._record_history(
            ticket.id,
            "CREATED",
            None,
            TicketStatus.RECEIVED.value,
            actor="webhook",
        )

        return ticket

    async def create_or_get(self, payload: TicketCreate) -> tuple[Ticket, bool]:
        """
        Idempotent creation.

        Returns:
            (ticket, created)
        """
        try:
            ticket = await self.create(payload)
            return ticket, True
        except DuplicateTicketError:
            existing = await self._repo.get_by_external_id(payload.external_id)
            if existing is None:
                raise
            return existing, False

    async def get(self, ticket_id: int) -> Ticket:
        ticket = await self._repo.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        return ticket

    async def get_by_external_id(self, external_id: str) -> Ticket | None:
        return await self._repo.get_by_external_id(external_id)

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        status_filter: TicketStatus | None = None,
    ) -> tuple[list[Ticket], int]:
        return await self._repo.list_paginated(page, limit, status_filter)

    async def get_history(self, ticket_id: int) -> list[TicketHistory]:
        await self.get(ticket_id)
        return await self._repo.list_history(ticket_id)

    async def transition(
        self,
        ticket_id: int,
        target: TicketStatus,
        actor: str = "system",
    ) -> Ticket:
        ticket = await self.get(ticket_id)
        self._assert_transition(ticket.status, target)

        old_status = ticket.status
        ticket.status = target
        ticket.updated_at = self._now()

        if target == TicketStatus.RESOLVED:
            ticket.resolved_at = self._now()

        await self._record_history(
            ticket.id,
            "STATUS_CHANGED",
            old_status.value,
            target.value,
            actor,
        )

        return await self._repo.update(ticket)

    async def attach_ai_result(
        self,
        ticket_id: int,
        ai: AIClassificationResult,
    ) -> Ticket:
        ticket = await self.get(ticket_id)

        ticket.ai_category = ai.category
        ticket.ai_urgency = ai.urgency
        ticket.ai_summary = ai.summary
        ticket.ai_confidence = ai.confidence
        ticket.ai_raw_response = ai.model_dump()
        ticket.updated_at = self._now()

        return await self._repo.update(ticket)

    async def set_ai_summary(self, ticket_id: int, summary: str) -> Ticket:
        ticket = await self.get(ticket_id)
        ticket.ai_summary = summary
        ticket.updated_at = self._now()
        return await self._repo.update(ticket)

    async def mark_auto_routed(
        self,
        ticket_id: int,
        assignee: str,
        actor: str = "ai",
    ) -> Ticket:
        ticket = await self.get(ticket_id)
        self._assert_transition(ticket.status, TicketStatus.AUTO_ROUTED)

        old_status = ticket.status
        ticket.assigned_to = assignee
        ticket.status = TicketStatus.AUTO_ROUTED
        ticket.updated_at = self._now()

        await self._record_history(
            ticket.id,
            "AUTO_ROUTED",
            old_status.value,
            TicketStatus.AUTO_ROUTED.value,
            actor,
        )

        return await self._repo.update(ticket)

    async def apply_review(
        self,
        ticket_id: int,
        decision: ReviewDecision,
        reviewer_email: str,
        comment: str | None,
    ) -> Ticket:
        ticket = await self.get(ticket_id)

        target = (
            TicketStatus.APPROVED
            if decision == ReviewDecision.APPROVED
            else TicketStatus.REJECTED
        )

        self._assert_transition(ticket.status, target)

        old_status = ticket.status
        ticket.reviewed_by = reviewer_email
        ticket.review_decision = decision
        ticket.review_comment = comment
        ticket.status = target
        ticket.updated_at = self._now()

        await self._record_history(
            ticket.id,
            "REVIEWED",
            old_status.value,
            target.value,
            reviewer_email,
        )

        return await self._repo.update(ticket)

    async def escalate(
        self,
        ticket_id: int,
        actor: str,
        comment: str | None,
    ) -> Ticket:
        ticket = await self.get(ticket_id)
        self._assert_transition(ticket.status, TicketStatus.ESCALATED)

        old_status = ticket.status
        ticket.status = TicketStatus.ESCALATED
        ticket.reviewed_by = actor
        ticket.review_comment = comment
        ticket.updated_at = self._now()

        await self._record_history(
            ticket.id,
            "ESCALATED",
            old_status.value,
            TicketStatus.ESCALATED.value,
            actor,
        )

        return await self._repo.update(ticket)

    async def assign(
        self,
        ticket_id: int,
        assignee: str,
        actor: str = "system",
    ) -> Ticket:
        ticket = await self.get(ticket_id)

        old_assignee = ticket.assigned_to
        ticket.assigned_to = assignee
        ticket.updated_at = self._now()

        await self._record_history(
            ticket.id,
            "ASSIGNED",
            old_assignee,
            assignee,
            actor,
        )

        return await self._repo.update(ticket)

    async def reprocess(self, ticket_id: int, actor: str = "admin") -> Ticket:
        """
        Retry AI classification for tickets whose AI step failed.

        Allowed only from MANUAL_REVIEW and only when ai_summary carries
        an error marker. Clears stale AI fields and returns ticket to RECEIVED
        so the background worker picks it up normally.
        """
        ticket = await self.get(ticket_id)

        if ticket.status != TicketStatus.MANUAL_REVIEW:
            raise InvalidStateTransitionError(
                ticket.status.value, TicketStatus.RECEIVED.value
            )

        if ticket.ai_summary not in REPROCESSABLE_AI_MARKERS:
            raise ReprocessNotAllowedError(ticket_id)

        ticket.ai_category = None
        ticket.ai_urgency = None
        ticket.ai_summary = None
        ticket.ai_confidence = None
        ticket.ai_raw_response = None

        return await self.transition(ticket_id, TicketStatus.RECEIVED, actor=actor)
