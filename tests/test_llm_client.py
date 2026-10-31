"""LLM client contract tests using httpx.MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest

from app.clients.llm_client import OpenAILLMClient
from app.config import Settings

VALID_PAYLOAD = {
    "category": "Technical",
    "urgency": "High",
    "summary": "Login failure",
    "confidence": 92,
    "requires_human_review": False,
    "missing_context": [],
}


def valid_payload(**overrides) -> dict:
    return {**VALID_PAYLOAD, **overrides}


# Base settings for all tests in this file
_BASE_SETTINGS = {
    "_env_file": None,
    "APP_NAME": "Test App",
    "DEBUG": False,
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "LLM_API_URL": "http://llm.test/v1/chat/completions",
    "LLM_API_KEY": "secret-key",
    "LLM_MODEL": "test-model",
    "LLM_TIMEOUT": 1,
    "LLM_MAX_RETRIES": 1,
    "LLM_ENABLE_JSON_MODE": True,
    "LLM_MAX_TOKENS": 300,
    "AI_CONFIDENCE_THRESHOLD": 80,
    "CORS_ORIGINS": ["*"],
    "ADMIN_API_KEY": "test-admin-key",
    "WEBHOOK_API_KEY": "test-webhook-key",
}


def make_settings(**overrides) -> Settings:
    """
    Create Settings instance with safe override handling.
    Accepts ONLY keyword arguments to avoid positional confusion.
    """
    final_kwargs = _BASE_SETTINGS.copy()
    final_kwargs.update(overrides)
    return Settings(**final_kwargs)


def make_client(handler, **settings_overrides) -> OpenAILLMClient:
    """
    Create OpenAILLMClient with mocked transport.

    Args:
        handler: Callable taking httpx.Request and returning httpx.Response.
        settings_overrides: Keyword args to override default test settings.
    """
    settings = make_settings(**settings_overrides)
    return OpenAILLMClient(
        settings=settings,
        transport=httpx.MockTransport(handler),
    )


async def test_classify_success_and_request_contract():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)

        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(valid_payload())}}]},
        )

    # Pass NO extra settings overrides here, just the handler
    client = make_client(handler)

    try:
        result = await client.classify("Login issue", "Cannot login")
    finally:
        await client.aclose()

    assert result is not None
    assert result.category == "Technical"
    assert result.urgency == "High"
    assert result.confidence == 92
    assert result.requires_human_review is False

    assert seen["auth"] == "Bearer secret-key"
    assert seen["body"]["model"] == "test-model"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["temperature"] == 0.0


async def test_low_confidence_forces_human_review():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                valid_payload(
                                    confidence=79, requires_human_review=False
                                )
                            )
                        }
                    }
                ]
            },
        )

    client = make_client(handler)

    try:
        result = await client.classify("Question", "What is this?")
    finally:
        await client.aclose()

    assert result is not None
    assert result.requires_human_review is True


async def test_invalid_json_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    client = make_client(handler)

    try:
        result = await client.classify("Subject", "Body")
    finally:
        await client.aclose()

    assert result is None


async def test_malformed_llm_structure_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"foo": "bar"})

    client = make_client(handler)

    try:
        result = await client.classify("Subject", "Body")
    finally:
        await client.aclose()

    assert result is None


async def test_pydantic_validation_failure_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"category": "Technical"})}}
                ]
            },
        )

    client = make_client(handler)

    try:
        result = await client.classify("Subject", "Body")
    finally:
        await client.aclose()

    assert result is None


async def test_timeout_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    client = make_client(handler)

    try:
        result = await client.classify("Subject", "Body")
    finally:
        await client.aclose()

    assert result is None


async def test_network_error_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down")

    client = make_client(handler)

    try:
        result = await client.classify("Subject", "Body")
    finally:
        await client.aclose()

    assert result is None


@pytest.mark.parametrize("status_code", [429, 500, 502, 503])
async def test_http_error_returns_none_when_retries_exhausted(status_code: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "failed"})

    # Override max retries to 1 for faster test
    client = make_client(handler, LLM_MAX_RETRIES=1)

    try:
        result = await client.classify("Subject", "Body")
    finally:
        await client.aclose()

    assert result is None


async def test_retry_then_success():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            return httpx.Response(500, json={"error": "temporary"})

        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(valid_payload())}}]},
        )

    # Need at least 2 attempts, so set retries to 2
    client = make_client(handler, LLM_MAX_RETRIES=2)

    try:
        result = await client.classify("Subject", "Body")
    finally:
        await client.aclose()

    assert attempts == 2
    assert result is not None
    assert result.category == "Technical"


async def test_json_mode_disabled_omits_response_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)

        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(valid_payload())}}]},
        )

    client = make_client(handler, LLM_ENABLE_JSON_MODE=False)

    try:
        result = await client.classify("Login issue", "Cannot login")
    finally:
        await client.aclose()

    assert result is not None
    assert "response_format" not in seen["body"]
