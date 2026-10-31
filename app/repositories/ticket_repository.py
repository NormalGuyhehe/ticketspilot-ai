"""Data access layer for tickets."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateTicketError
from app.database.models import Ticket, TicketHistory, TicketStatus


class TicketRepository:
    """
    All SQLAlchemy queries for tickets.

    No business logic here.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, ticket: Ticket) -> Ticket:
        self._db.add(ticket)

        try:
            await self._db.flush()
        except IntegrityError as exc:
            await self._db.rollback()
            raise DuplicateTicketError(ticket.external_id) from exc

        await self._db.refresh(ticket)
        return ticket

    async def get_by_id(self, ticket_id: int) -> Ticket | None:
        result = await self._db.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Ticket | None:
        result = await self._db.execute(
            select(Ticket).where(Ticket.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        page: int = 1,
        limit: int = 20,
        status_filter: TicketStatus | None = None,
    ) -> tuple[list[Ticket], int]:
        query = select(Ticket)
        count_query = select(func.count()).select_from(Ticket)

        if status_filter is not None:
            query = query.where(Ticket.status == status_filter)
            count_query = count_query.where(Ticket.status == status_filter)

        query = query.order_by(Ticket.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)

        items_result = await self._db.execute(query)
        total_result = await self._db.execute(count_query)

        return list(items_result.scalars().all()), total_result.scalar_one()

    async def add_history(self, history: TicketHistory) -> None:
        self._db.add(history)
        await self._db.flush()

    async def list_history(self, ticket_id: int) -> list[TicketHistory]:
        result = await self._db.execute(
            select(TicketHistory)
            .where(TicketHistory.ticket_id == ticket_id)
            .order_by(TicketHistory.timestamp.asc())
        )
        return list(result.scalars().all())

    async def update(self, ticket: Ticket) -> Ticket:
        await self._db.flush()
        await self._db.refresh(ticket)
        return ticket
