"""Routing service tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import RoutingRule
from app.repositories.routing_repository import RoutingRepository
from app.services.routing_service import RoutingService


def make_settings() -> Settings:
    return Settings(_env_file=None)


async def test_default_assignee_for_known_category(db_session: AsyncSession):
    service = RoutingService(RoutingRepository(db_session), make_settings())

    assignee = await service.resolve_assignee("Technical", "High")

    assert assignee == "tech-support@example.com"


async def test_default_assignee_for_unknown_category(db_session: AsyncSession):
    service = RoutingService(RoutingRepository(db_session), make_settings())

    assignee = await service.resolve_assignee("Unknown", "Low")

    assert assignee == "general-support@example.com"


async def test_active_rule_overrides_default(db_session: AsyncSession):
    rule = RoutingRule(
        category="Billing",
        urgency="High",
        assignee_email="priority-billing@example.com",
        priority=10,
        is_active=True,
    )
    db_session.add(rule)
    await db_session.flush()

    service = RoutingService(RoutingRepository(db_session), make_settings())
    assignee = await service.resolve_assignee("Billing", "High")

    assert assignee == "priority-billing@example.com"


async def test_inactive_rule_is_ignored(db_session: AsyncSession):
    rule = RoutingRule(
        category="Billing",
        urgency="High",
        assignee_email="inactive@example.com",
        priority=10,
        is_active=False,
    )
    db_session.add(rule)
    await db_session.flush()

    service = RoutingService(RoutingRepository(db_session), make_settings())
    assignee = await service.resolve_assignee("Billing", "High")

    assert assignee == "billing-team@example.com"


async def test_highest_priority_rule_wins(db_session: AsyncSession):
    low = RoutingRule(
        category="Technical",
        urgency="Medium",
        assignee_email="low@example.com",
        priority=1,
        is_active=True,
    )
    high = RoutingRule(
        category="Technical",
        urgency="Medium",
        assignee_email="high@example.com",
        priority=100,
        is_active=True,
    )

    db_session.add_all([low, high])
    await db_session.flush()

    service = RoutingService(RoutingRepository(db_session), make_settings())
    assignee = await service.resolve_assignee("Technical", "Medium")

    assert assignee == "high@example.com"
