"""Deterministic local ``LLMClientProtocol`` adapter for offline demo runs."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from quadkit import serialization
from quadkit.ai.llm.types import Completion, LLMError, StreamChunk, TokenUsage
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.result import Ok, Result


class DeterministicExtractionLLMClient:
    """Offline ``LLMClientProtocol`` implementation returning schema-valid JSON.

    In production, ``LLMModule.configure(ClientConfig(provider="anthropic", ...))``
    binds a cloud or Ollama client to the same ``LLMClientProtocol`` token;
    service code stays identical.
    """

    def __init__(self, *, model: str) -> None:
        self._model = model
        self.calls = 0

    async def complete(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        _ = kwargs
        self.calls += 1
        user_text = str(messages[-1].get("content", "")) if messages else ""
        lowered = user_text.lower()

        if any(word in lowered for word in ("urgent", "outage", "failing", "sev1")):
            category = "incident"
            severity = "high"
            actions = ["Page on-call engineer", "Verify payment gateway status"]
        elif any(word in lowered for word in ("invoice", "refund", "billing")):
            category = "billing"
            severity = "medium"
            actions = ["Inspect ledger entry", "Send billing confirmation"]
        else:
            category = "general"
            severity = "low"
            actions = ["Reply with documentation link"]

        raw_note = user_text.splitlines()[-1].strip() or "Support note"
        payload = serialization.dumps_str(
            {
                "category": category,
                "severity": severity,
                "summary": raw_note[:120],
                "action_items": actions,
            }
        )
        prompt_tokens = max(12, len(user_text.split()) * 2)
        completion_tokens = max(16, len(payload.split()) * 2)
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return Ok(
            Completion(
                content=payload,
                model=self._model,
                provider="deterministic",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                usage=usage,
            )
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        result = await self.complete(messages, **kwargs)
        completion = result.unwrap()
        yield StreamChunk(content=completion.content, is_final=True)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        _ = timeout
        return HealthCheckResult(
            component="deterministic_llm",
            status=HealthStatus.HEALTHY,
            details={"model": self._model},
        )

    async def close(self) -> None:
        return None


__all__ = ["DeterministicExtractionLLMClient"]
