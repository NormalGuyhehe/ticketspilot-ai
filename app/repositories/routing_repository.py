"""Data access layer for routing rules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import RoutingRule


class RoutingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_active_rule(
        self,
        category: str,
        urgency: str,
    ) -> RoutingRule | None:
        result = await self._db.execute(
            select(RoutingRule)
            .where(
                RoutingRule.category == category,
                RoutingRule.urgency == urgency,
                RoutingRule.is_active.is_(True),
            )
            .order_by(RoutingRule.priority.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
