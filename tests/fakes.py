"""Test fakes for external clients."""

from __future__ import annotations

from app.schemas.ai import AIClassificationResult


class FakeLLMClient:
    """
    Fake LLM client.

    Implements same contract as LLMClient Protocol.
    By default emulates business rule:
    confidence < threshold => requires_human_review = True.
    """

    def __init__(
        self,
        response: AIClassificationResult | None = None,
        *,
        enforce_threshold: bool = True,
        threshold: int = 80,
    ) -> None:
        self.response = response
        self.enforce_threshold = enforce_threshold
        self.threshold = threshold
        self.calls: list[tuple[str, str]] = []

    async def classify(self, subject: str, body: str) -> AIClassificationResult | None:
        self.calls.append((subject, body))

        if self.response is None:
            return None

        if (
            self.enforce_threshold
            and self.response.confidence < self.threshold
            and not self.response.requires_human_review
        ):
            return self.response.model_copy(update={"requires_human_review": True})

        return self.response

    async def aclose(self) -> None:
        return None
