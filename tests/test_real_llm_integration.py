"""Optional real LLM integration smoke test."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest

from app.clients.llm_client import OpenAILLMClient
from app.config import Settings

LOCAL_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
}


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_local_endpoint(url: str | None) -> bool:
    if not url:
        return False

    try:
        host = urlparse(url).hostname
    except ValueError:
        return False

    return host in LOCAL_HOSTS


def _has_real_llm_target() -> bool:
    """
    Real LLM test is enabled when:
    - RUN_REAL_LLM_TESTS is true;
    - and either API key is present OR endpoint is local.

    Local llama.cpp/Ollama endpoints do not require an API key.
    """
    enabled = _bool_env("RUN_REAL_LLM_TESTS", False)
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    url = os.getenv("LLM_API_URL", "")

    return enabled and (bool(api_key) or _is_local_endpoint(url))


@pytest.mark.integration
@pytest.mark.skipif(
    not _has_real_llm_target(),
    reason=(
        "Set RUN_REAL_LLM_TESTS=1 and either LLM_API_KEY/OPENAI_API_KEY "
        "or a local LLM_API_URL such as http://127.0.0.1:8080/..."
    ),
)
async def test_real_llm_classifies_support_ticket() -> None:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

    settings = Settings(
        _env_file=None,
        LLM_API_KEY=api_key,
        LLM_API_URL=os.getenv(
            "LLM_API_URL",
            "https://api.openai.com/v1/chat/completions",
        ),
        LLM_MODEL=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        LLM_TIMEOUT=int(os.getenv("LLM_TIMEOUT", "15")),
        LLM_MAX_RETRIES=int(os.getenv("LLM_MAX_RETRIES", "2")),
        LLM_ENABLE_JSON_MODE=_bool_env("LLM_ENABLE_JSON_MODE", True),
        LLM_MAX_TOKENS=int(os.getenv("LLM_MAX_TOKENS", "300")),
        AI_CONFIDENCE_THRESHOLD=int(os.getenv("AI_CONFIDENCE_THRESHOLD", "80")),
    )

    client = OpenAILLMClient(settings)

    try:
        result = await client.classify(
            subject="Duplicate invoice charge",
            body=(
                "Hello, I was charged twice for my monthly subscription. "
                "Please refund the duplicate payment."
            ),
        )
    finally:
        await client.aclose()

    assert result is not None
    assert result.category in {"Billing", "Technical", "General", "Feature", "Bug"}
    assert result.urgency in {"Low", "Medium", "High"}
    assert 0 <= result.confidence <= 100
    assert isinstance(result.requires_human_review, bool)
    assert isinstance(result.missing_context, list)
