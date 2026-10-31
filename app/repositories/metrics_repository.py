"""Data access layer for metrics."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ReviewDecision, Ticket, TicketStatus


class MetricsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def status_counts(self) -> dict[TicketStatus, int]:
        result = await self._db.execute(
            select(Ticket.status, func.count()).group_by(Ticket.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def review_counts(self) -> dict[ReviewDecision, int]:
        result = await self._db.execute(
            select(Ticket.review_decision, func.count())
            .where(Ticket.review_decision.isnot(None))
            .group_by(Ticket.review_decision)
        )
        return {row[0]: row[1] for row in result.all()}

    async def resolved_intervals(self) -> list[tuple[datetime, datetime]]:
        result = await self._db.execute(
            select(Ticket.created_at, Ticket.resolved_at).where(
                Ticket.resolved_at.isnot(None)
            )
        )
        return [(row[0], row[1]) for row in result.all()]
