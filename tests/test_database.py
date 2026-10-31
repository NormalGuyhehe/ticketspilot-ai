"""Database session lifecycle tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.database.models import Ticket, TicketStatus


async def test_session_scope_commits_on_success(application):
    async with application.database.session_scope() as db:
        db.add(
            Ticket(
                external_id="db-commit-1",
                customer_email="user@example.com",
                subject="Commit",
                body="Body",
                status=TicketStatus.RECEIVED,
            )
        )

    async with application.database.session_scope() as db:
        result = await db.execute(
            select(Ticket).where(Ticket.external_id == "db-commit-1")
        )
        assert result.scalar_one_or_none() is not None


async def test_session_scope_rolls_back_on_exception(application):
    with pytest.raises(RuntimeError):
        async with application.database.session_scope() as db:
            db.add(
                Ticket(
                    external_id="db-rollback-1",
                    customer_email="user@example.com",
                    subject="Rollback",
                    body="Body",
                    status=TicketStatus.RECEIVED,
                )
            )
            raise RuntimeError("boom")

    async with application.database.session_scope() as db:
        result = await db.execute(
            select(Ticket).where(Ticket.external_id == "db-rollback-1")
        )
        assert result.scalar_one_or_none() is None
