"""Pydantic contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ai import AIClassificationResult
from app.schemas.ticket import TicketCreate


def test_ticket_create_rejects_invalid_email():
    with pytest.raises(ValidationError):
        TicketCreate(
            external_id="schema-1",
            customer_email="not-an-email",
            subject="Test",
            body="Test",
        )


def test_ticket_create_requires_external_id():
    with pytest.raises(ValidationError):
        TicketCreate(
            customer_email="user@example.com",
            subject="Test",
            body="Test",
        )


def test_ai_confidence_must_be_within_bounds():
    with pytest.raises(ValidationError):
        AIClassificationResult(
            category="Technical",
            urgency="High",
            summary="Ok",
            confidence=101,
            requires_human_review=False,
            missing_context=[],
        )

    with pytest.raises(ValidationError):
        AIClassificationResult(
            category="Technical",
            urgency="High",
            summary="Ok",
            confidence=-1,
            requires_human_review=False,
            missing_context=[],
        )


def test_ai_summary_max_length_is_enforced():
    with pytest.raises(ValidationError):
        AIClassificationResult(
            category="Technical",
            urgency="High",
            summary="x" * 201,
            confidence=90,
            requires_human_review=False,
            missing_context=[],
        )
