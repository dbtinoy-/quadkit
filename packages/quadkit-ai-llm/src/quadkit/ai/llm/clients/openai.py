"""OpenAI LLM client implementation.

Production-ready implementation with OpenAI API integration.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime
from typing import Any

from quadkit.ai.llm.clients._tools_utils import (
    parse_openai_tool_calls,
    serialize_message_for_openai,
    tool_to_openai_format,
)
from quadkit.ai.llm.clients.base import AbstractLLMClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMError,
    LLMModelNotFoundError,
    LLMQuotaExceededError,
    LLMRateLimitError,
)
from quadkit.ai.llm.types import (
    AIError,
    ChatMessage,
    Completion,
    StreamChunk,
    ThinkingResult,
    TokenUsage,
)
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.result import Err, Ok, Result


class OpenAIClient(AbstractLLMClient):
    """OpenAI LLM client implementation.

    Conforms to: :class:`~quadkit.contracts.ai.LLMClientProtocol` protocol via structural typing.

    Supports GPT-4, GPT-3.5-Turbo, and other OpenAI models with:
    - Streaming responses
    - Function/tool calling
    - Vision models
    - Automatic retry with exponential backoff
    - Error handling and rate limit management

    Example:
        >>> from the optional provider module import ClientConfig
        >>> config = ClientConfig(provider="openai", model="gpt-4-turbo")
        >>> client = OpenAIClient(config)
        >>> completion = await client.complete([
        ...     ChatMessage(role="user", content="Hello!")
        ... ])
    """

    def __init__(self, config: ClientConfig):
        """Initialize OpenAI client.

        Args:
            config: LLM configuration

        Raises:
            ImportError: If openai package is not installed
        """
        self.config = config

        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError(
                "OpenAI client requires 'openai' package. "
                "Install with: pip install quadkit-ai-llm[openai]",
            ) from e

        api_key = config.api_key.get_secret_value() if config.api_key else None
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=config.api_base,
            timeout=config.timeout,
        )
        super().__init__(config=config)

    async def _do_complete(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate completion from messages.

        Args:
            messages: Chat messages
            **kwargs: Additional OpenAI API parameters (temperature, max_tokens, etc.)

        Returns:
            ``Ok(Completion)`` on success.
            ``Err(LLMRateLimitError | LLMQuotaExceededError | LLMContentFilterError
            | LLMModelNotFoundError)`` for recoverable domain failures.

        Raises:
            LLMAuthenticationError: If API key is invalid.
            AIError: For unexpected infrastructure failures.
        """
        try:
            # Convert messages to OpenAI format
            openai_messages = [self._convert_message(msg) for msg in messages]

            # Pop positional overrides so **kwargs doesn't contain duplicates
            _model = kwargs.pop("model", self.config.model)
            _max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)
            _temperature = kwargs.pop("temperature", self.config.temperature)
            _tools = kwargs.pop("tools", None)

            params: dict[str, Any] = {
                "model": _model,
                "messages": openai_messages,
                **kwargs,
            }
            if _max_tokens is not None:
                params["max_tokens"] = _max_tokens
            if _tools:
                params["tools"] = [
                    converted
                    for tool in _tools
                    if (converted := tool_to_openai_format(tool)) is not None
                ]

            self._apply_thinking(params)
            if "reasoning_effort" not in params:
                params["temperature"] = _temperature

            # Make API call
            response = await self.client.chat.completions.create(**params)

            # Validate response structure
            if not hasattr(response, "choices") or not response.choices:
                msg = "OpenAI returned an invalid response structure"
                raise AIError(msg)

            # Convert to our Completion type
            choice = response.choices[0]
            tool_calls = parse_openai_tool_calls(
                getattr(choice.message, "tool_calls", None)
            )
            # DeepSeek-style providers surface reasoning on the message object
            reasoning_content: str | None = getattr(
                choice.message, "reasoning_content", None
            )
            # OpenAI o-series: track reasoning token count if available
            reasoning_tokens: int | None = None
            if response.usage:
                details = getattr(response.usage, "completion_tokens_details", None)
                if details and hasattr(details, "reasoning_tokens"):
                    reasoning_tokens = details.reasoning_tokens
            thinking: ThinkingResult | None = (
                ThinkingResult(content=reasoning_content or "", tokens=reasoning_tokens)
                if (reasoning_content or reasoning_tokens is not None)
                else None
            )

            return Ok(
                Completion(
                    content=choice.message.content or "",
                    model=response.model,
                    finish_reason=choice.finish_reason,
                    tool_calls=tool_calls,
                    thinking=thinking,
                    usage=(
                        TokenUsage(
                            prompt_tokens=response.usage.prompt_tokens,
                            completion_tokens=response.usage.completion_tokens,
                            total_tokens=response.usage.total_tokens,
                        )
                        if response.usage
                        else None
                    ),
                    metadata={
                        "id": response.id,
                        "created": response.created,
                        "system_fingerprint": response.system_fingerprint,
                    },
                    timestamp=datetime.now(UTC),
                )
            )

        except Exception as e:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(e)

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[AsyncIterator[StreamChunk], LLMError]:
        """Start a streaming completion.

        Args:
            messages: Chat messages
            **kwargs: Additional OpenAI API parameters

        Returns:
            ``Ok(AsyncIterator[StreamChunk])`` on successful connection.
            ``Err(LLMError)`` if the connection could not be established.
            Mid-stream errors propagate as exceptions from the iterator.

        Raises:
            LLMAuthenticationError: If API key is invalid.
            AIError: For unexpected infrastructure failures.
        """
        try:
            # Convert messages to OpenAI format
            openai_messages = [self._convert_message(msg) for msg in messages]

            # Pop positional overrides so **kwargs doesn't contain duplicates
            _model = kwargs.pop("model", self.config.model)
            _max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)
            _temperature = kwargs.pop("temperature", self.config.temperature)

            params: dict[str, Any] = {
                "model": _model,
                "messages": openai_messages,
                "stream": True,
                **kwargs,
            }
            if _max_tokens is not None:
                params["max_tokens"] = _max_tokens

            self._apply_thinking(params)
            if "reasoning_effort" not in params:
                params["temperature"] = _temperature

            # Establish stream — this is where connection-level errors surface
            stream = await self.client.chat.completions.create(**params)
            return Ok(self._stream_impl(stream))

        except Exception as e:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(e)

    async def _stream_impl(self, stream: Any) -> AsyncGenerator[StreamChunk, None]:
        """Yield StreamChunk objects from an established OpenAI stream.

        Handles both standard text deltas and DeepSeek-style
        ``reasoning_content`` deltas, emitting thinking chunks first.
        """
        index = 0
        async for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            # DeepSeek-style providers emit reasoning_content on the delta
            thinking = getattr(choice.delta, "reasoning_content", None)
            if thinking:
                yield StreamChunk(
                    thinking_delta=thinking,
                    is_thinking=True,
                    model=chunk.model,
                    finish_reason=choice.finish_reason,
                    index=index,
                )
                index += 1
            elif choice.delta.content:
                yield StreamChunk(
                    delta=choice.delta.content,
                    model=chunk.model,
                    finish_reason=choice.finish_reason,
                    index=index,
                )
                index += 1

    async def _do_chat(
        self,
        messages: list[ChatMessage],
        tools: list[Any] | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate completion with optional tool/function calling.

        Tool calling is handled by :meth:`_do_complete` via
        ``complete(..., tools=...)``; this method forwards the tool
        descriptors to keep the ``chat`` code path consistent.

        Args:
            messages: Chat messages
            tools: Optional list of tools the LLM can call
            **kwargs: Additional OpenAI API parameters

        Returns:
            ``Ok(Completion)`` on success.  ``Err(LLMError)`` for recoverable
            failures.
        """
        return await self._do_complete(messages, tools=tools, **kwargs)

    def _apply_thinking(self, params: dict[str, Any]) -> None:
        """Inject thinking/reasoning parameters into the API payload.

        For suppression (``ThinkingConfig.suppress=True``): injects
        ``enable_thinking: false`` and ``chat_template_kwargs.enable_thinking: false``
        into ``extra_body`` so LM Studio, vLLM, SGLang and similar OpenAI-compatible
        backends skip chain-of-thought generation.

        For OpenAI o-series effort (``ThinkingConfig.effort``): sets
        ``reasoning_effort`` and removes ``temperature`` (OpenAI rejects that
        combination for reasoning models).

        Args:
            params: Mutable API payload dict modified in-place.
        """
        if self.config.thinking is None:
            return
        if self.config.thinking.suppress:
            existing = params.get("extra_body") or {}
            params["extra_body"] = {
                **existing,
                "enable_thinking": False,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            return
        if self.config.thinking.effort:
            params["reasoning_effort"] = self.config.thinking.effort
            params.pop("temperature", None)

    def _convert_message(self, msg: ChatMessage) -> dict[str, Any]:
        """Convert ChatMessage to OpenAI message format.

        Args:
            msg: ChatMessage to convert

        Returns:
            OpenAI message dict
        """
        return serialize_message_for_openai(msg)

    def _handle_error_as_result(self, error: Exception) -> Result[Any, LLMError]:
        """Map a caught exception to ``Err`` (recoverable) or re-raise (infra).

        Recoverable failures → ``Err(LLMRecoverableError)``.
        Infrastructure failures → raised directly.
        """
        err_str = str(error).lower()
        if "authentication" in err_str or "api key" in err_str:
            raise LLMAuthenticationError("OpenAI authentication failed") from None
        if "rate limit" in err_str:
            return Err(LLMRateLimitError("OpenAI rate limit exceeded"))
        if (
            "quota" in err_str
            or "billing" in err_str
            or "insufficient_quota" in err_str
        ):
            return Err(LLMQuotaExceededError("OpenAI quota exceeded"))
        if "content" in err_str and ("filter" in err_str or "policy" in err_str):
            return Err(LLMContentFilterError("OpenAI content filter"))
        if "model" in err_str and (
            "not found" in err_str or "does not exist" in err_str
        ):
            return Err(LLMModelNotFoundError("OpenAI model not found"))
        raise AIError("OpenAI infrastructure error") from None

    async def close(self) -> None:
        """Close the OpenAI client and cleanup resources."""
        if not self._closed:
            await self.client.close()
            await super().close()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check.

        Returns:
            Structured health check result.
        """
        if self._closed:
            return HealthCheckResult(
                component="llm.openai",
                status=HealthStatus.UNHEALTHY,
                error="Client is closed",
            )

        return HealthCheckResult(
            component="llm.openai",
            status=HealthStatus.HEALTHY,
            details={
                "provider": "openai",
                "model": self.config.model,
            },
        )
