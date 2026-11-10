"""Base class for Quadkit LLM clients.

Provides common retry, exponential backoff, circuit breaker, and token limit
checks for all LLM providers. Subclasses implement provider-specific logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import AsyncIterator
import types
from typing import Any, Protocol, Self, cast

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    sanitize_llm_error,
)
from quadkit.ai.llm.health import ProviderCircuitBreaker
from quadkit.ai.llm.thinking import normalize_thinking_text
from quadkit.ai.llm.types import (
    ChatMessage,
    Completion,
    StreamChunk,
    ToolCall,
)
from quadkit.contracts.ai.thinking import ThinkingResult
from quadkit.contracts.core.health import HealthCheckResult
from quadkit.contracts.infra import AsyncStream
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


def _sanitize_llm_exception(error: Exception) -> LLMError:
    """Map a raised provider exception to a safe LLM error."""
    return sanitize_llm_error(error)


class _ClientCircuitBreaker(Protocol):
    async def is_available(self) -> bool: ...
    async def record_success(self) -> None: ...
    async def record_failure(self, error: Exception) -> None: ...


class AbstractLLMClient(ABC):
    """Base class for all LLM client implementations.

    Provides common retry, backoff, circuit breaker, and pre-flight token
    checking. Subclasses implement only provider-specific API calls and
    response parsing via `_do_complete` and `_do_stream_chat`.
    """

    def __init__(
        self,
        config: ClientConfig,
        max_retries: int = 3,
        circuit_breaker: _ClientCircuitBreaker | None = None,
    ):
        """Initialize the base client with config.

        Args:
            config: LLM configuration object.
            max_retries: Maximum number of retries for transient errors.
            circuit_breaker: Optional circuit breaker for resilience.
                             If not provided, creates a default ProviderCircuitBreaker.
        """
        self.config = config
        self.max_retries = max_retries
        self._circuit_breaker = circuit_breaker or ProviderCircuitBreaker(
            provider_name=config.provider.value
        )
        self._closed = False

    async def complete(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Template method: retry + circuit breaker + pre-flight + subclass."""

        if not await self._circuit_breaker.is_available():
            return Err(LLMError("Circuit breaker is open due to recent failures."))

        if await self._exceeds_token_limit(messages, **kwargs):
            return Err(LLMError("Request exceeds model maximum context window."))

        for attempt in range(self.max_retries + 1):
            try:
                result = await self._do_complete(messages, **kwargs)
                if result.is_ok():
                    await self._circuit_breaker.record_success()
                    return Ok(self._normalize_thinking(result.unwrap()))

                err = result.unwrap_err()
                if self._is_retryable_error(err):
                    await self._circuit_breaker.record_failure(err)
                    if attempt < self.max_retries:
                        await self._backoff(attempt)
                        continue

                return Err(
                    sanitize_llm_error(err)
                )  # Non-retryable or max retries reached

            except Exception as e:
                await self._circuit_breaker.record_failure(e)
                if not self._is_retryable_exception(e) or attempt == self.max_retries:
                    raise _sanitize_llm_exception(e) from None
                await self._backoff(attempt)

        return Err(LLMError("Max retries exceeded"))

    def stream_chat(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> AsyncStream[StreamChunk, LLMError]:
        """Template method for streaming chat with retry + circuit breaker.

        Returns an ``AsyncStream`` immediately. All setup, retry, and
        circuit-breaker logic is executed lazily inside the stream's async
        generator. Setup failures and mid-stream failures are both surfaced
        through ``AsyncStream``'s typed error channel.
        """

        async def _establish_stream() -> AsyncIterator[StreamChunk]:
            """Async generator that handles setup, retry, and streaming."""
            # Check circuit breaker
            if not await self._circuit_breaker.is_available():
                raise LLMError("Circuit breaker is open due to recent failures.")

            # Check token limit
            if await self._exceeds_token_limit(messages, **kwargs):
                raise LLMError("Request exceeds model maximum context window.")

            # A stream cannot be safely restarted after emitting data: doing
            # so can duplicate output or hide a mid-stream provider failure.
            emitted_chunk = False

            # Retry loop for setup
            for attempt in range(self.max_retries + 1):
                try:
                    result = await self._do_stream_chat(messages, **kwargs)
                    if result.is_ok():
                        await self._circuit_breaker.record_success()
                        stream_iter = result.unwrap()
                        # Stream the chunks with timeout
                        async for chunk in self._timeout_stream(
                            stream_iter, self.config.timeout / 2
                        ):
                            emitted_chunk = True
                            yield chunk
                        return

                    err = result.unwrap_err()
                    if self._is_retryable_error(err):
                        await self._circuit_breaker.record_failure(err)
                        if attempt < self.max_retries:
                            await self._backoff(attempt)
                            continue

                    raise err

                except Exception as e:
                    await self._circuit_breaker.record_failure(e)
                    if (
                        emitted_chunk
                        or not self._is_retryable_exception(e)
                        or attempt == self.max_retries
                    ):
                        raise
                    await self._backoff(attempt)

            raise LLMError("Max retries exceeded")

        return AsyncStream(
            _establish_stream(),
            error_adapter=self._coerce_stream_error,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolCall] | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Template method: completion with tools."""

        if not await self._circuit_breaker.is_available():
            return Err(LLMError("Circuit breaker is open due to recent failures."))

        if await self._exceeds_token_limit(messages, **kwargs):
            return Err(LLMError("Request exceeds model maximum context window."))

        for attempt in range(self.max_retries + 1):
            try:
                result = await self._do_chat(messages, tools, **kwargs)
                if result.is_ok():
                    await self._circuit_breaker.record_success()
                    return Ok(self._normalize_thinking(result.unwrap()))

                err = result.unwrap_err()
                if self._is_retryable_error(err):
                    await self._circuit_breaker.record_failure(err)
                    if attempt < self.max_retries:
                        await self._backoff(attempt)
                        continue

                return Err(sanitize_llm_error(err))

            except Exception as e:
                await self._circuit_breaker.record_failure(e)
                if not self._is_retryable_exception(e) or attempt == self.max_retries:
                    raise _sanitize_llm_exception(e) from None
                await self._backoff(attempt)

        return Err(LLMError("Max retries exceeded"))

    async def _timeout_stream(
        self, stream: AsyncIterator[StreamChunk], chunk_timeout: float
    ) -> AsyncIterator[StreamChunk]:
        """Wrap an async iterator with a per-chunk timeout."""
        try:
            while True:
                chunk = await asyncio.wait_for(anext(stream), timeout=chunk_timeout)
                yield chunk
        except StopAsyncIteration:
            return
        except TimeoutError:
            logger.warning("Stream chunk timed out after %s seconds", chunk_timeout)
            raise LLMError("Streaming timed out between chunks")

    def _coerce_stream_error(self, exc: Exception) -> LLMError:
        """Convert iterator failures into typed, sanitized stream errors."""
        return _sanitize_llm_exception(exc)

    def _is_retryable_error(self, err: LLMError) -> bool:
        """Determine if a returned error should trigger a retry.

        Rate limits and request timeouts are NOT retried: the router's
        cascade advances to the next entry instead of hammering a throttled
        or overloaded model in place (a timeout retry costs another full
        timeout window).
        """
        if isinstance(err, (LLMRateLimitError, LLMTimeoutError)):
            return False
        if "connection" in str(err).lower() or "timeout" in str(err).lower():
            return True
        return "503" in str(err) or "502" in str(err) or "504" in str(err)

    def _is_retryable_exception(self, e: Exception) -> bool:
        """Determine if a raised exception should trigger a retry.

        Rate limits and request timeouts fail fast (cascade advancement
        handles them); authentication and validation errors are permanent.
        """
        if isinstance(e, (LLMRateLimitError, LLMTimeoutError)):
            return False
        if isinstance(e, LLMAuthenticationError):
            return False
        return not ("invalid" in str(e).lower() or "not found" in str(e).lower())

    async def _backoff(self, attempt: int) -> None:
        """Apply exponential backoff before the next retry."""
        delay = (2**attempt) + (0.1 * attempt)  # basic jitter
        logger.info("Applying backoff of %.2fs before retry %d", delay, attempt + 1)
        await asyncio.sleep(delay)

    async def _exceeds_token_limit(
        self, messages: list[ChatMessage], **kwargs: Any
    ) -> bool:
        """Pre-flight check: return True if messages exceed the configured context window.

        Uses :class:`~quadkit.ai.llm.pricing.tokens.TiktokenCounter` for accurate
        model-specific counting (falls back to character estimation when tiktoken is
        unavailable). The check is skipped if ``context_window`` is not set in
        ``config.extra``.

        Args:
            messages: Chat messages to count.
            **kwargs: Ignored; accepted for call-site compatibility.

        Returns:
            ``True`` when the token count exceeds the context window limit,
            ``False`` otherwise (including when no limit is configured).
        """
        context_window: int | None = self.config.extra.get("context_window")
        if context_window is None:
            return False

        from quadkit.ai.llm.pricing.tokens import TiktokenCounter

        counter = TiktokenCounter(model=self.config.model)
        token_count = counter.count_messages(messages)
        return token_count > context_window

    async def close(self) -> None:
        """Close the client and cleanup resources."""
        self._closed = True

    def _apply_thinking(self, params: dict[str, Any]) -> None:
        """Inject provider-specific thinking parameters into an API payload dict.

        Called from ``_do_complete``, ``_do_stream_chat``, and ``_do_chat`` in
        each provider immediately after the base payload is assembled and before
        the API call is made.  The default implementation is a no-op so providers
        without thinking support require no change.

        Override in providers that support extended thinking/reasoning to avoid
        repeating the injection logic across all three call-path methods.

        Args:
            params: Mutable API payload dict that will be sent to the provider.
        """

    def _normalize_thinking(self, completion: Completion) -> Completion:
        """Strip inline thinking tags from completion content and populate ThinkingResult.

        This method is a universal post-processing step applied in the
        ``complete()`` and ``chat()`` template methods to ALL clients. It handles
        models that embed reasoning tokens directly in their text output using
        known tag formats (Qwen3 ``<think>``, Gemma-4 ``<|channel>thought``, etc.).

        Guard: if ``completion.thinking`` is already set (Anthropic, Gemini, Bedrock,
        OpenRouter all extract thinking natively from structured API fields), this
        method returns the completion unchanged — normalization is a no-op for them.

        Args:
            completion: Raw completion from ``_do_complete`` or ``_do_chat``.

        Returns:
            A new Completion with clean ``content`` and populated ``thinking``,
            or the original unchanged if no inline thinking was detected.
        """
        if completion.thinking is not None:
            return completion

        content = completion.content
        if not content:
            # No text content (e.g. a pure tool-call response) — nothing to
            # normalize.  ``content`` is typed ``str`` but provider responses
            # for tool calls legitimately carry ``None``.
            return completion

        clean_content, thinking_text = normalize_thinking_text(content)
        if thinking_text is None:
            return completion

        return cast(
            "Completion",
            completion.model_copy(
                update={
                    "content": clean_content,
                    "thinking": ThinkingResult(content=thinking_text),
                }
            ),
        )

    @abstractmethod
    async def _do_complete(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Provider-specific complete implementation."""

    @abstractmethod
    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[AsyncIterator[StreamChunk], LLMError]:
        """Provider-specific streaming implementation."""

    @abstractmethod
    async def _do_chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolCall] | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Provider-specific chat (with tools) implementation."""

    @abstractmethod
    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check against the provider."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        await self.close()
