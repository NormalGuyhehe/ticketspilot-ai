"""Application service container."""

from __future__ import annotations

import logging

from app.clients.llm_client import LLMClient, OpenAILLMClient
from app.config import Settings
from app.database.models import TicketStatus
from app.database.session import Database
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.routing_repository import RoutingRepository
from app.repositories.ticket_repository import TicketRepository
from app.services.metrics_service import MetricsService
from app.services.routing_service import RoutingService
from app.services.ticket_processing_service import TicketProcessingService
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    App-scoped container.

    Stores expensive/shared dependencies:
    - Settings
    - Database
    - LLM client

    Creates request-scoped services on demand.
    """

    def __init__(
        self,
        settings: Settings,
        database: Database,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self._llm_client = llm_client or OpenAILLMClient(settings)

    @property
    def llm_client(self) -> LLMClient:
        return self._llm_client

    async def aclose(self) -> None:
        await self._llm_client.aclose()

    def make_ticket_service(self, db) -> TicketService:
        return TicketService(TicketRepository(db))

    def make_routing_service(self, db) -> RoutingService:
        return RoutingService(RoutingRepository(db), self.settings)

    def make_metrics_service(self, db) -> MetricsService:
        return MetricsService(MetricsRepository(db))

    def make_processing_service(self, db) -> TicketProcessingService:
        return TicketProcessingService(
            ticket_service=self.make_ticket_service(db),
            routing_service=self.make_routing_service(db),
            llm_client=self._llm_client,
        )

    async def process_ticket_background(self, ticket_id: int) -> None:
        """
        Background entrypoint.

        IMPORTANT:
        Does not use request-scoped session.
        Opens its own session scope.
        """
        try:
            async with self.database.session_scope() as db:
                service = self.make_processing_service(db)
                await service.process(ticket_id)
        except Exception:
            logger.exception("Background processing failed for ticket %s", ticket_id)
            await self._mark_manual_review_after_error(ticket_id)

    async def _mark_manual_review_after_error(self, ticket_id: int) -> None:
        """
        Best-effort recovery.

        If background processing crashed, ticket must not stay PROCESSING.
        Move it to MANUAL_REVIEW with SYSTEM_ERROR marker.
        """
        try:
            async with self.database.session_scope() as db:
                ticket_service = self.make_ticket_service(db)
                ticket = await ticket_service.get(ticket_id)

                if ticket.status != TicketStatus.PROCESSING:
                    return

                await ticket_service.transition(
                    ticket_id,
                    TicketStatus.MANUAL_REVIEW,
                    actor="system-error",
                )
                await ticket_service.set_ai_summary(
                    ticket_id,
                    "SYSTEM_ERROR",
                )
        except Exception:
            logger.exception(
                "Failed to recover ticket %s after background processing error",
                ticket_id,
            )
