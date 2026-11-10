"""Streaming response adapters for unified multi-provider streaming.

Provides a unified interface for streaming responses from different LLM
providers, with automatic chunk aggregation, token tracking, and metrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from quadkit.ai.llm.streaming.stream_response import (
    StreamingMetrics,
    StreamingResponse,
)
from quadkit.ai.llm.types import StreamChunk
from quadkit.contracts.ai.models import ModelRequest
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

__all__ = [
    "AbstractStreamingAdapter",
    "AnthropicStreamingAdapter",
    "GoogleStreamingAdapter",
    "OpenAIStreamingAdapter",
    "StreamingMetrics",
    "StreamingOrchestrator",
    "StreamingResponse",
]


class AbstractStreamingAdapter(ABC):
    """Abstract base for streaming response adapters.

    Provides a unified interface for streaming from different
    LLM providers. Concrete implementations wrap provider-specific
    streaming clients.
    """

    def __init__(self, provider: str) -> None:
        """Initialize streaming adapter.

        Args:
            provider: Provider name
        """
        self.provider = provider

    @abstractmethod
    def stream(
        self,
        request: ModelRequest,
        model_id: str,
    ) -> AsyncIterator[StreamChunk]:
        """Stream response from LLM provider.

        Args:
            request: The model request
            model_id: Model to use

        Yields:
            StreamChunk objects as they arrive

        Raises:
            StreamingError: If streaming fails
        """

    async def stream_to_response(
        self,
        request: ModelRequest,
        model_id: str,
    ) -> StreamingResponse:
        """Stream and aggregate response into StreamingResponse.

        Args:
            request: The model request
            model_id: Model to use

        Returns:
            Completed StreamingResponse with all chunks

        Raises:
            StreamingError: If streaming fails
        """
        response = StreamingResponse(self.provider, model_id)

        async for chunk in self.stream(request, model_id):
            response.add_chunk(chunk)

        response.finish()
        logger.info("stream_completed", total_chunks=len(response.chunks))

        return response


class OpenAIStreamingAdapter(AbstractStreamingAdapter):
    """Streaming adapter for OpenAI provider."""

    async def stream(
        self,
        request: ModelRequest,
        model_id: str,
    ) -> AsyncIterator[StreamChunk]:
        """Stream response from OpenAI.

        Args:
            request: The model request
            model_id: Model to use

        Yields:
            StreamChunk objects as they arrive
        """

        # Placeholder: In real implementation, call OpenAI streaming API
        # For now, simulate a few chunks
        async def generate_chunks() -> AsyncIterator[StreamChunk]:
            chunks = [
                StreamChunk(delta="Hello ", index=0),
                StreamChunk(delta="from ", index=1),
                StreamChunk(delta="OpenAI", index=2, finish_reason="stop"),
            ]
            for chunk in chunks:
                await asyncio.sleep(0.01)  # Simulate network latency
                yield chunk

        async for chunk in generate_chunks():
            yield chunk


class AnthropicStreamingAdapter(AbstractStreamingAdapter):
    """Streaming adapter for Anthropic provider."""

    async def stream(
        self,
        request: ModelRequest,
        model_id: str,
    ) -> AsyncIterator[StreamChunk]:
        """Stream response from Anthropic.

        Args:
            request: The model request
            model_id: Model to use

        Yields:
            StreamChunk objects as they arrive
        """

        # Placeholder: In real implementation, call Anthropic streaming API
        async def generate_chunks() -> AsyncIterator[StreamChunk]:
            chunks = [
                StreamChunk(delta="Hello ", index=0),
                StreamChunk(delta="from ", index=1),
                StreamChunk(delta="Anthropic", index=2, finish_reason="end_turn"),
            ]
            for chunk in chunks:
                await asyncio.sleep(0.01)
                yield chunk

        async for chunk in generate_chunks():
            yield chunk


class GoogleStreamingAdapter(AbstractStreamingAdapter):
    """Streaming adapter for Google provider."""

    async def stream(
        self,
        request: ModelRequest,
        model_id: str,
    ) -> AsyncIterator[StreamChunk]:
        """Stream response from Google.

        Args:
            request: The model request
            model_id: Model to use

        Yields:
            StreamChunk objects as they arrive
        """

        # Placeholder: In real implementation, call Google streaming API
        async def generate_chunks() -> AsyncIterator[StreamChunk]:
            chunks = [
                StreamChunk(delta="Hello ", index=0),
                StreamChunk(delta="from ", index=1),
                StreamChunk(delta="Google", index=2, finish_reason="stop"),
            ]
            for chunk in chunks:
                await asyncio.sleep(0.01)
                yield chunk

        async for chunk in generate_chunks():
            yield chunk


class StreamingOrchestrator:
    """Orchestrates streaming across multiple providers.

    Similar to LLMOrchestrator but for streaming responses,
    with automatic provider fallback and metrics tracking.
    """

    def __init__(self) -> None:
        """Initialize streaming orchestrator."""
        self.adapters: dict[str, AbstractStreamingAdapter] = {}
        self.lock = asyncio.Lock()
        logger.info("streaming_orchestrator_created")

    async def register_adapter(
        self,
        provider: str,
        adapter: AbstractStreamingAdapter,
    ) -> None:
        """Register a streaming adapter for a provider.

        Args:
            provider: Provider name
            adapter: AbstractStreamingAdapter implementation
        """
        async with self.lock:
            self.adapters[provider] = adapter
            logger.info(
                "streaming_adapter_registered",
                adapter_type=type(adapter).__name__,
            )

    async def stream(
        self,
        request: ModelRequest,
        provider: str,
        model_id: str,
    ) -> StreamingResponse:
        """Stream response from a provider.

        Args:
            request: The model request
            provider: Provider to use
            model_id: Model to use

        Returns:
            Completed StreamingResponse

        Raises:
            ValueError: If provider not registered
            StreamingError: If streaming fails
        """
        if provider not in self.adapters:
            raise ValueError("No streaming adapter is available")

        adapter = self.adapters[provider]
        response = await adapter.stream_to_response(request, model_id)

        logger.info("stream_orchestrated")

        return response

    async def stream_with_fallback(
        self,
        request: ModelRequest,
        providers: list[str],
        model_ids: dict[str, str],
    ) -> StreamingResponse:
        """Stream with automatic fallback to alternate providers.

        Tries providers in order until one succeeds.

        Args:
            request: The model request
            providers: List of providers to try in order
            model_ids: Dict mapping provider to model_id

        Returns:
            Completed StreamingResponse from first successful provider

        Raises:
            ValueError: If no providers available or streaming fails
        """
        last_error_type: str | None = None

        for provider in providers:
            if provider not in self.adapters:
                logger.warning("streaming_provider_not_registered")
                continue

            try:
                model_id = model_ids.get(provider)
                if not model_id:
                    logger.warning("streaming_provider_no_model")
                    continue

                response = await self.stream(request, provider, model_id)
                logger.info("stream_fallback_success")

                return response

            except Exception as e:  # noqa: BLE001
                last_error_type = type(e).__name__
                logger.warning(
                    "streaming_provider_failed",
                    error_type=last_error_type,
                )
                continue

        details = f" (last error type: {last_error_type})" if last_error_type else ""
        logger.error(
            "streaming_all_providers_failed",
            last_error_type=last_error_type,
        )
        raise ValueError(f"Streaming failed for all providers{details}") from None

    async def stream_with_chunking(
        self,
        request: ModelRequest,
        provider: str,
        model_id: str,
        chunk_callback: Callable[[StreamChunk], Awaitable[None]] | None = None,
    ) -> StreamingResponse:
        """Stream with callback for each chunk (no aggregation).

        Useful for real-time processing of chunks without waiting
        for full response.

        Args:
            request: The model request
            provider: Provider to use
            model_id: Model to use
            chunk_callback: Async callback(chunk) for each chunk

        Returns:
            Completed StreamingResponse
        """
        if provider not in self.adapters:
            raise ValueError("No streaming adapter is available")

        adapter = self.adapters[provider]
        response = StreamingResponse(provider, model_id)

        async for chunk in adapter.stream(request, model_id):
            response.add_chunk(chunk)
            if chunk_callback:
                await chunk_callback(chunk)

        response.finish()
        return response
