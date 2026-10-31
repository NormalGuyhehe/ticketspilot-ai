"""Configuration tests."""

from __future__ import annotations

from app.config import Settings


def test_settings_have_safe_defaults():
    assert Settings.model_fields["APP_NAME"].default == "TicketPilot AI"
    assert Settings.model_fields["AI_CONFIDENCE_THRESHOLD"].default == 80
    assert Settings.model_fields["LLM_MAX_RETRIES"].default == 2


def test_build_settings_allows_overrides():
    from app.config import build_settings

    settings = build_settings(
        APP_NAME="Override",
        AI_CONFIDENCE_THRESHOLD=70,
        _env_file=None,
    )

    assert settings.APP_NAME == "Override"
    assert settings.AI_CONFIDENCE_THRESHOLD == 70
