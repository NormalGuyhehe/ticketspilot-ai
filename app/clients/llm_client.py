"""LLM client abstraction."""

from __future__ import annotations

import json
import logging
from typing import Protocol

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings
from app.schemas.ai import AIClassificationResult

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base LLM client error."""


class LLMUnavailableError(LLMClientError):
    """LLM API cannot be reached."""


class LLMInvalidResponseError(LLMClientError):
    """LLM returned unparseable response."""


class LLMClient(Protocol):
    """
    Contract for LLM clients.

    Enables DI and testability.
    """

    async def classify(
        self, subject: str, body: str
    ) -> AIClassificationResult | None: ...

    async def aclose(self) -> None: ...


class OpenAILLMClient:
    """
    OpenAI-compatible LLM client.

    Works with:
    - OpenAI
    - Azure OpenAI compatible endpoint
    - Local Ollama OpenAI-compatible API
    - vLLM OpenAI-compatible API
    """

    SYSTEM_PROMPT = (
        "You are a support ticket classifier. Analyze the ticket and return STRICT JSON only.\n"
        "Categories: Billing | Technical | General | Feature | Bug\n"
        "Urgency: Low | Medium | High\n"
        "Confidence: 0-100 reflecting how sure you are of the classification.\n"
        "Set requires_human_review=true if the ticket is ambiguous, missing critical context, "
        "or confidence < 80."
    )

    USER_PROMPT_TEMPLATE = """Classify this support ticket:

    Subject: {subject}
    Body: {body}

    Return JSON with fields:
    - category (string)
    - urgency (string)
    - summary (string, max 200 chars)
    - confidence (int 0-100)
    - requires_human_review (bool)
    - missing_context (list of strings, empty if none)"""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_url = settings.LLM_API_URL
        self._model = settings.LLM_MODEL
        self._confidence_threshold = settings.AI_CONFIDENCE_THRESHOLD
        self._max_retries = max(1, settings.LLM_MAX_RETRIES)
        self._enable_json_mode = settings.LLM_ENABLE_JSON_MODE
        self._max_tokens = settings.LLM_MAX_TOKENS

        timeout = httpx.Timeout(float(settings.LLM_TIMEOUT), connect=5.0)

        headers = {"Content-Type": "application/json"}
        if settings.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _extract_content(data: dict) -> dict:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMInvalidResponseError(
                f"Malformed LLM response structure: {exc}"
            ) from exc

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMInvalidResponseError(f"LLM returned invalid JSON: {exc}") from exc

    async def _request(self, subject: str, body: str) -> dict:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": self.USER_PROMPT_TEMPLATE.format(
                        subject=subject,
                        body=body,
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": self._max_tokens,
            "stream": False,
        }

        if self._enable_json_mode:
            payload["response_format"] = {"type": "json_object"}

        result: dict | None = None

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_exception(_should_retry_llm_error),
            reraise=True,
        ):
            with attempt:
                response = await self._client.post(self._api_url, json=payload)
                response.raise_for_status()
                result = self._extract_content(response.json())

        if result is None:
            raise LLMInvalidResponseError("LLM request completed without result")

        return result

    async def classify(self, subject: str, body: str) -> AIClassificationResult | None:
        """
        Classify ticket via LLM.

        Returns None on failure.
        Caller must route ticket to MANUAL_REVIEW if None is returned.
        """
        try:
            raw = await self._request(subject, body)
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.HTTPStatusError,
            LLMClientError,
        ) as exc:
            logger.warning(
                "LLM API unavailable, falling back to manual review: %s", exc
            )
            return None
        except Exception as exc:
            logger.exception("Unexpected LLM error: %s", exc)
            return None

        try:
            result = AIClassificationResult.model_validate(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pydantic validation failed for LLM output: %s", exc)
            return None

        if result.confidence < self._confidence_threshold:
            result.requires_human_review = True

        return result


def _should_retry_llm_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code == 429 or status_code >= 500

    return False
