"""Routing logic - resolves assignee based on AI classification."""

from __future__ import annotations

import logging

from app.config import Settings
from app.repositories.routing_repository import RoutingRepository

logger = logging.getLogger(__name__)

DEFAULT_ASSIGNEES: dict[str, str] = {
    "Billing": "billing-team@example.com",
    "Technical": "tech-support@example.com",
    "General": "general-support@example.com",
    "Feature": "product-team@example.com",
    "Bug": "tech-support@example.com",
}


class RoutingService:
    def __init__(
        self,
        repo: RoutingRepository,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._settings = settings

    async def resolve_assignee(self, category: str, urgency: str) -> str:
        rule = await self._repo.find_active_rule(category, urgency)
        if rule is not None:
            return rule.assignee_email

        return DEFAULT_ASSIGNEES.get(category, "general-support@example.com")
