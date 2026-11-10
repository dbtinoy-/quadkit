"""No-op LLM client for testing and stubbed deployments."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

from quadkit.ai.llm.clients.base import AbstractLLMClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import LLMError
from quadkit.ai.llm.types import ChatMessage, Completion, StreamChunk
from quadkit.contracts.ai import ToolCall
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.result import Ok, Result


class NoOpLLMClient(AbstractLLMClient):
    """LLM client that never talks to a provider.

    Every call resolves to a deterministic, in-memory response so the
    subsystem can boot and be exercised without SDK credentials.
    """

    def __init__(self, config: ClientConfig | None = None) -> None:
        super().__init__(config or ClientConfig())

    async def _do_complete(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        return Ok(
            Completion(
                content="",
                model=self.config.model,
                usage=None,
            )
        )

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[AsyncIterator[StreamChunk], LLMError]:
        # Generator function returning an empty async stream; the import
        # guard above keeps this branch dead in normal operation.
        async def _empty() -> AsyncIterator[StreamChunk]:
            for _ in ():
                yield cast("StreamChunk", None)

        return Ok(_empty())

    async def _do_chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolCall] | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        return await self._do_complete(messages, **kwargs)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        return HealthCheckResult(component="llm", status=HealthStatus.HEALTHY)


__all__ = ["NoOpLLMClient"]
