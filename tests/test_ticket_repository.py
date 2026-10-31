"""Repository-level tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateTicketError
from app.database.models import Ticket, TicketHistory, TicketStatus
from app.repositories.ticket_repository import TicketRepository


def make_ticket(
    external_id: str,
    *,
    status: TicketStatus = TicketStatus.RECEIVED,
    created_at: datetime | None = None,
) -> Ticket:
    return Ticket(
        external_id=external_id,
        customer_email="user@example.com",
        subject="Repo test",
        body="Repo body",
        status=status,
        created_at=created_at or datetime.now(UTC),
    )


async def test_create_and_get_by_id(db_session: AsyncSession):
    repo = TicketRepository(db_session)
    ticket = await repo.create(make_ticket("repo-1"))

    assert ticket.id is not None

    fetched = await repo.get_by_id(ticket.id)
    assert fetched is not None
    assert fetched.external_id == "repo-1"


async def test_get_by_external_id(db_session: AsyncSession):
    repo = TicketRepository(db_session)
    created = await repo.create(make_ticket("repo-external"))

    fetched = await repo.get_by_external_id("repo-external")
    assert fetched is not None
    assert fetched.id == created.id


async def test_duplicate_external_id_raises_and_preserves_original(
    db_session: AsyncSession,
):
    repo = TicketRepository(db_session)

    first = await repo.create(make_ticket("repo-dup"))
    first_id = first.id
    await db_session.commit()

    with pytest.raises(DuplicateTicketError):
        await repo.create(make_ticket("repo-dup"))

    fetched = await repo.get_by_external_id("repo-dup")
    assert fetched is not None
    assert fetched.id == first_id


async def test_list_paginated_orders_by_created_at_desc(
    db_session: AsyncSession,
):
    repo = TicketRepository(db_session)
    now = datetime.now(UTC)

    t1 = await repo.create(make_ticket("page-1", created_at=now - timedelta(minutes=3)))
    t2 = await repo.create(make_ticket("page-2", created_at=now - timedelta(minutes=2)))
    t3 = await repo.create(make_ticket("page-3", created_at=now - timedelta(minutes=1)))

    await db_session.commit()

    items, total = await repo.list_paginated(page=1, limit=2)

    assert total == 3
    assert [item.id for item in items] == [t3.id, t2.id]

    items_page2, total_page2 = await repo.list_paginated(page=2, limit=2)
    assert total_page2 == 3
    assert [item.id for item in items_page2] == [t1.id]


async def test_list_paginated_filters_by_status(db_session: AsyncSession):
    repo = TicketRepository(db_session)

    await repo.create(make_ticket("filter-received", status=TicketStatus.RECEIVED))
    await repo.create(make_ticket("filter-manual", status=TicketStatus.MANUAL_REVIEW))
    await db_session.commit()

    items, total = await repo.list_paginated(
        page=1,
        limit=10,
        status_filter=TicketStatus.MANUAL_REVIEW,
    )

    assert total == 1
    assert items[0].external_id == "filter-manual"


async def test_history_is_ordered_by_timestamp(db_session: AsyncSession):
    repo = TicketRepository(db_session)
    ticket = await repo.create(make_ticket("history-1"))
    await db_session.commit()

    now = datetime.now(UTC)

    await repo.add_history(
        TicketHistory(
            ticket_id=ticket.id,
            action="LATER",
            old_value=None,
            new_value="B",
            actor="system",
            timestamp=now + timedelta(minutes=1),
        )
    )

    await repo.add_history(
        TicketHistory(
            ticket_id=ticket.id,
            action="EARLIER",
            old_value=None,
            new_value="A",
            actor="system",
            timestamp=now,
        )
    )

    history = await repo.list_history(ticket.id)

    assert [item.action for item in history] == ["EARLIER", "LATER"]


async def test_update_persists_changes(db_session: AsyncSession):
    repo = TicketRepository(db_session)
    ticket = await repo.create(make_ticket("update-1"))
    await db_session.commit()

    ticket.subject = "Updated subject"
    updated = await repo.update(ticket)

    assert updated.subject == "Updated subject"
