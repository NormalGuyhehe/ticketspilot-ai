"""Seed local database with demo tickets. No real PII."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# -----------------------------------------------------------------------------
# Import bootstrap.
#
# When this file is executed as a script, Python puts scripts/ into sys.path[0],
# not the project root. This makes `from app...` imports fail.
# We explicitly add project root to sys.path.
# -----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.app import TicketsPilotApplication
from app.config import build_settings
from app.database.base import Base
from app.database.models import (
    ReviewDecision,
    RoutingRule,
    Ticket,
    TicketHistory,
    TicketStatus,
)

ROUTING_RULES: list[dict[str, Any]] = [
    {
        "category": "Billing",
        "urgency": "High",
        "assignee_email": "billing-escalations@example.com",
        "priority": 100,
        "is_active": True,
    },
    {
        "category": "Technical",
        "urgency": "High",
        "assignee_email": "tech-oncall@example.com",
        "priority": 90,
        "is_active": True,
    },
    {
        "category": "General",
        "urgency": "Low",
        "assignee_email": "general-support@example.com",
        "priority": 10,
        "is_active": True,
    },
]


DEMO_TICKETS: list[dict[str, Any]] = [
    {
        "external_id": "demo-001",
        "customer_email": "customer-1@example.com",
        "subject": "Duplicate invoice charge",
        "body": (
            "Hello, I was charged twice for my monthly subscription. "
            "Please refund the duplicate payment."
        ),
        "status": TicketStatus.MANUAL_REVIEW,
        "ai_category": "Billing",
        "ai_urgency": "High",
        "ai_summary": "Customer reports duplicate billing charge and requests refund.",
        "ai_confidence": 72,
        "ai_raw_response": {
            "category": "Billing",
            "urgency": "High",
            "summary": "Customer reports duplicate billing charge and requests refund.",
            "confidence": 72,
            "requires_human_review": True,
            "missing_context": ["invoice_id"],
        },
        "assigned_to": None,
        "reviewed_by": None,
        "review_decision": None,
        "review_comment": None,
        "created_offset_minutes": 30,
        "updated_offset_minutes": 28,
        "resolved_offset_minutes": None,
        "history": [
            {
                "action": "CREATED",
                "old_value": None,
                "new_value": TicketStatus.RECEIVED.value,
                "actor": "webhook",
                "offset_minutes": 30,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.RECEIVED.value,
                "new_value": TicketStatus.PROCESSING.value,
                "actor": "background-worker",
                "offset_minutes": 29,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.PROCESSING.value,
                "new_value": TicketStatus.MANUAL_REVIEW.value,
                "actor": "background-worker",
                "offset_minutes": 28,
            },
        ],
    },
    {
        "external_id": "demo-002",
        "customer_email": "customer-2@example.com",
        "subject": "Cannot login to account",
        "body": (
            "I enter the correct password but the login button does nothing. "
            "I tried Chrome and Firefox."
        ),
        "status": TicketStatus.AUTO_ROUTED,
        "ai_category": "Technical",
        "ai_urgency": "High",
        "ai_summary": "Login button unresponsive despite valid credentials.",
        "ai_confidence": 94,
        "ai_raw_response": {
            "category": "Technical",
            "urgency": "High",
            "summary": "Login button unresponsive despite valid credentials.",
            "confidence": 94,
            "requires_human_review": False,
            "missing_context": [],
        },
        "assigned_to": "tech-oncall@example.com",
        "reviewed_by": None,
        "review_decision": None,
        "review_comment": None,
        "created_offset_minutes": 25,
        "updated_offset_minutes": 23,
        "resolved_offset_minutes": None,
        "history": [
            {
                "action": "CREATED",
                "old_value": None,
                "new_value": TicketStatus.RECEIVED.value,
                "actor": "webhook",
                "offset_minutes": 25,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.RECEIVED.value,
                "new_value": TicketStatus.PROCESSING.value,
                "actor": "background-worker",
                "offset_minutes": 24,
            },
            {
                "action": "AUTO_ROUTED",
                "old_value": TicketStatus.PROCESSING.value,
                "new_value": TicketStatus.AUTO_ROUTED.value,
                "actor": "background-worker",
                "offset_minutes": 23,
            },
        ],
    },
    {
        "external_id": "demo-003",
        "customer_email": "customer-3@example.com",
        "subject": "How to export reports?",
        "body": "Where can I export monthly usage reports to CSV?",
        "status": TicketStatus.RESOLVED,
        "ai_category": "General",
        "ai_urgency": "Low",
        "ai_summary": "Customer asks how to export usage reports to CSV.",
        "ai_confidence": 91,
        "ai_raw_response": {
            "category": "General",
            "urgency": "Low",
            "summary": "Customer asks how to export usage reports to CSV.",
            "confidence": 91,
            "requires_human_review": False,
            "missing_context": [],
        },
        "assigned_to": "general-support@example.com",
        "reviewed_by": None,
        "review_decision": None,
        "review_comment": None,
        "created_offset_minutes": 60,
        "updated_offset_minutes": 5,
        "resolved_offset_minutes": 5,
        "history": [
            {
                "action": "CREATED",
                "old_value": None,
                "new_value": TicketStatus.RECEIVED.value,
                "actor": "webhook",
                "offset_minutes": 60,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.RECEIVED.value,
                "new_value": TicketStatus.PROCESSING.value,
                "actor": "background-worker",
                "offset_minutes": 59,
            },
            {
                "action": "AUTO_ROUTED",
                "old_value": TicketStatus.PROCESSING.value,
                "new_value": TicketStatus.AUTO_ROUTED.value,
                "actor": "background-worker",
                "offset_minutes": 58,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.AUTO_ROUTED.value,
                "new_value": TicketStatus.RESOLVED.value,
                "actor": "support-agent@example.com",
                "offset_minutes": 5,
            },
        ],
    },
    {
        "external_id": "demo-004",
        "customer_email": "customer-4@example.com",
        "subject": "Password reset email not received",
        "body": "I requested a password reset but did not receive the email.",
        "status": TicketStatus.APPROVED,
        "ai_category": "Technical",
        "ai_urgency": "Medium",
        "ai_summary": "Password reset email not delivered to customer.",
        "ai_confidence": 68,
        "ai_raw_response": {
            "category": "Technical",
            "urgency": "Medium",
            "summary": "Password reset email not delivered to customer.",
            "confidence": 68,
            "requires_human_review": True,
            "missing_context": ["customer_account_id"],
        },
        "assigned_to": None,
        "reviewed_by": "operator@example.com",
        "review_decision": ReviewDecision.APPROVED,
        "review_comment": "AI classification accepted after checking spam folder guidance.",
        "created_offset_minutes": 20,
        "updated_offset_minutes": 10,
        "resolved_offset_minutes": None,
        "history": [
            {
                "action": "CREATED",
                "old_value": None,
                "new_value": TicketStatus.RECEIVED.value,
                "actor": "webhook",
                "offset_minutes": 20,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.RECEIVED.value,
                "new_value": TicketStatus.PROCESSING.value,
                "actor": "background-worker",
                "offset_minutes": 19,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.PROCESSING.value,
                "new_value": TicketStatus.MANUAL_REVIEW.value,
                "actor": "background-worker",
                "offset_minutes": 18,
            },
            {
                "action": "REVIEWED",
                "old_value": TicketStatus.MANUAL_REVIEW.value,
                "new_value": TicketStatus.APPROVED.value,
                "actor": "operator@example.com",
                "offset_minutes": 10,
            },
        ],
    },
    {
        "external_id": "demo-005",
        "customer_email": "customer-5@example.com",
        "subject": "Question about pricing",
        "body": "Do you offer annual billing discounts?",
        "status": TicketStatus.REJECTED,
        "ai_category": "Technical",
        "ai_urgency": "Low",
        "ai_summary": "Customer asks about pricing discounts.",
        "ai_confidence": 55,
        "ai_raw_response": {
            "category": "Technical",
            "urgency": "Low",
            "summary": "Customer asks about pricing discounts.",
            "confidence": 55,
            "requires_human_review": True,
            "missing_context": [],
        },
        "assigned_to": None,
        "reviewed_by": "operator@example.com",
        "review_decision": ReviewDecision.REJECTED,
        "review_comment": "Incorrect category. This is Billing/Sales, not Technical.",
        "created_offset_minutes": 15,
        "updated_offset_minutes": 7,
        "resolved_offset_minutes": None,
        "history": [
            {
                "action": "CREATED",
                "old_value": None,
                "new_value": TicketStatus.RECEIVED.value,
                "actor": "webhook",
                "offset_minutes": 15,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.RECEIVED.value,
                "new_value": TicketStatus.PROCESSING.value,
                "actor": "background-worker",
                "offset_minutes": 14,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.PROCESSING.value,
                "new_value": TicketStatus.MANUAL_REVIEW.value,
                "actor": "background-worker",
                "offset_minutes": 13,
            },
            {
                "action": "REVIEWED",
                "old_value": TicketStatus.MANUAL_REVIEW.value,
                "new_value": TicketStatus.REJECTED.value,
                "actor": "operator@example.com",
                "offset_minutes": 7,
            },
        ],
    },
    {
        "external_id": "demo-006",
        "customer_email": "customer-6@example.com",
        "subject": "Production API returning 500 errors",
        "body": (
            "Our integration started receiving intermittent 500 errors from the API. "
            "This is affecting production traffic."
        ),
        "status": TicketStatus.ESCALATED,
        "ai_category": "Bug",
        "ai_urgency": "High",
        "ai_summary": "Intermittent production API 500 errors reported.",
        "ai_confidence": 82,
        "ai_raw_response": {
            "category": "Bug",
            "urgency": "High",
            "summary": "Intermittent production API 500 errors reported.",
            "confidence": 82,
            "requires_human_review": True,
            "missing_context": ["request_ids", "region"],
        },
        "assigned_to": None,
        "reviewed_by": "lead@example.com",
        "review_decision": None,
        "review_comment": "Escalated to L2 due to production impact.",
        "created_offset_minutes": 12,
        "updated_offset_minutes": 4,
        "resolved_offset_minutes": None,
        "history": [
            {
                "action": "CREATED",
                "old_value": None,
                "new_value": TicketStatus.RECEIVED.value,
                "actor": "webhook",
                "offset_minutes": 12,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.RECEIVED.value,
                "new_value": TicketStatus.PROCESSING.value,
                "actor": "background-worker",
                "offset_minutes": 11,
            },
            {
                "action": "STATUS_CHANGED",
                "old_value": TicketStatus.PROCESSING.value,
                "new_value": TicketStatus.MANUAL_REVIEW.value,
                "actor": "background-worker",
                "offset_minutes": 10,
            },
            {
                "action": "ESCALATED",
                "old_value": TicketStatus.MANUAL_REVIEW.value,
                "new_value": TicketStatus.ESCALATED.value,
                "actor": "lead@example.com",
                "offset_minutes": 4,
            },
        ],
    },
]


async def _ensure_routing_rules(db) -> int:
    """Insert routing rules only if they do not already exist."""
    result = await db.execute(select(RoutingRule.category, RoutingRule.urgency))
    existing = {(row[0], row[1]) for row in result.all()}

    inserted = 0

    for rule in ROUTING_RULES:
        key = (rule["category"], rule["urgency"])
        if key in existing:
            continue

        db.add(RoutingRule(**rule))
        inserted += 1

    await db.flush()
    return inserted


async def _seed_ticket(db, data: dict[str, Any], now: datetime) -> bool:
    """Insert one demo ticket if external_id does not exist."""
    external_id = data["external_id"]

    existing = await db.execute(
        select(Ticket.id).where(Ticket.external_id == external_id)
    )

    if existing.scalar_one_or_none() is not None:
        return False

    meta_keys = {
        "history",
        "created_offset_minutes",
        "updated_offset_minutes",
        "resolved_offset_minutes",
    }

    ticket_values = {key: value for key, value in data.items() if key not in meta_keys}

    created_at = now - timedelta(minutes=data["created_offset_minutes"])
    updated_at = now - timedelta(minutes=data["updated_offset_minutes"])

    resolved_offset = data.get("resolved_offset_minutes")
    resolved_at = (
        now - timedelta(minutes=resolved_offset)
        if resolved_offset is not None
        else None
    )

    ticket = Ticket(
        **ticket_values,
        created_at=created_at,
        updated_at=updated_at,
        resolved_at=resolved_at,
    )

    db.add(ticket)
    await db.flush()
    await db.refresh(ticket)

    for item in data.get("history", []):
        db.add(
            TicketHistory(
                ticket_id=ticket.id,
                action=item["action"],
                old_value=item.get("old_value"),
                new_value=item.get("new_value"),
                actor=item["actor"],
                timestamp=now - timedelta(minutes=item["offset_minutes"]),
            )
        )

    await db.flush()
    return True


async def main() -> None:
    settings = build_settings()
    application = TicketsPilotApplication(settings)

    try:
        # For local/demo seeding it is acceptable to ensure schema exists.
        # In production schema should be managed by Alembic migrations.
        async with application.database.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with application.database.session_scope() as db:
            rules_inserted = await _ensure_routing_rules(db)

            now = datetime.now(UTC)
            tickets_inserted = 0

            for ticket_data in DEMO_TICKETS:
                if await _seed_ticket(db, ticket_data, now):
                    tickets_inserted += 1

        print(
            "Seed completed: "
            f"routing_rules_added={rules_inserted}, "
            f"tickets_added={tickets_inserted}"
        )

    finally:
        await application.container.aclose()
        await application.database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
