"""Anthropic Claude LLM client implementation.

Production-ready implementation with Anthropic API integration.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime
from typing import Any

from quadkit.ai.llm.clients._anthropic_requests import (
    _tool_result_text,
    _tool_to_anthropic,
)
from quadkit.ai.llm.clients._message_utils import serialize_content_for_anthropic
from quadkit.ai.llm.clients._tools_utils import parse_json_arguments
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
    FunctionCall,
    Role,
    StreamChunk,
    ThinkingResult,
    TokenUsage,
    ToolCall,
)
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.result import Err, Ok, Result
from quadkit.serialization import dumps_str


class AnthropicClient(AbstractLLMClient):
    """Anthropic Claude LLM client implementation.

    Conforms to: :class:`~quadkit.contracts.ai.LLMClientProtocol` protocol via structural typing.

    Supports Claude 3 (Opus, Sonnet, Haiku) models with:
    - Streaming responses
    - Tool calling
    - Vision capabilities
    - Automatic retry and error handling

    Example:
        >>> from the optional provider module import ClientConfig
        >>> config = ClientConfig(provider="anthropic", model="claude-3-sonnet-20240229")
        >>> client = AnthropicClient(config)
        >>> completion = await client.complete([
        ...     ChatMessage(role="user", content="Hello!")
        ... ])
    """

    def __init__(self, config: ClientConfig):
        """Initialize Anthropic client.

        Args:
            config: LLM configuration

        Raises:
            ImportError: If anthropic package is not installed
        """
        super().__init__(config=config)

        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise ImportError(
                "Anthropic client requires 'anthropic' package. "
                "Install with: pip install quadkit-ai-llm[anthropic]",
            ) from e

        api_key = config.api_key.get_secret_value() if config.api_key else None
        self.client = AsyncAnthropic(
            api_key=api_key,
            base_url=config.api_base,
            timeout=config.timeout,
        )

    async def _do_complete(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate completion from messages.

        Args:
            messages: Chat messages
            **kwargs: Additional Anthropic API parameters

        Returns:
            ``Ok(Completion)`` on success.  ``Err(LLMError)`` for recoverable
            failures (rate limit, quota, content filter, model not found).

        Raises:
            LLMAuthenticationError: If API key is invalid.
            AIError: For unexpected infrastructure failures.
        """
        try:
            # Extract system message if present
            system_msg = None
            conv_messages = []
            for msg in messages:
                if msg.role == Role.SYSTEM:
                    system_msg = msg.content
                else:
                    conv_messages.append(self._convert_message(msg))

            # Build thinking param; suppress temperature (incompatible with thinking)
            params = {
                "model": kwargs.pop("model", self.config.model),
                "messages": conv_messages,
                "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens or 1024),
                **kwargs,
            }
            self._apply_thinking(params)
            if "thinking" not in params:
                params["temperature"] = kwargs.pop(
                    "temperature", self.config.temperature
                )

            tools = params.pop("tools", None)
            if tools:
                converted_tools = [_tool_to_anthropic(t) for t in tools]
                params["tools"] = [t for t in converted_tools if t.get("name")]

            if system_msg:
                params["system"] = system_msg

            # Make API call
            response = await self.client.messages.create(**params)

            # Parse content blocks: separate thinking blocks from text blocks
            content = ""
            thinking: ThinkingResult | None = None
            thinking_parts: list[str] = []
            thinking_signature: str | None = None
            tool_calls: list[ToolCall] = []
            for block in response.content:
                block_type = getattr(block, "type", None)
                if block_type == "thinking":
                    thinking_parts.append(getattr(block, "thinking", "") or "")
                    thinking_signature = getattr(block, "signature", None)
                elif block_type == "text" or (
                    block_type is None and hasattr(block, "text")
                ):
                    content = getattr(block, "text", "")
                elif block_type == "tool_use":
                    tool_calls.append(
                        ToolCall(
                            id=getattr(block, "id", ""),
                            type="function",
                            function=FunctionCall(
                                name=getattr(block, "name", ""),
                                arguments=dumps_str(getattr(block, "input", {})),
                            ),
                        )
                    )
            if thinking_parts:
                thinking = ThinkingResult(
                    content="".join(thinking_parts),
                    signature=thinking_signature,
                )

            return Ok(
                Completion(
                    content=content,
                    model=response.model,
                    finish_reason=response.stop_reason,
                    thinking=thinking,
                    tool_calls=tool_calls or None,
                    usage=TokenUsage(
                        prompt_tokens=response.usage.input_tokens,
                        completion_tokens=response.usage.output_tokens,
                        total_tokens=response.usage.input_tokens
                        + response.usage.output_tokens,
                    ),
                    metadata={
                        "id": response.id,
                        "type": response.type,
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
            **kwargs: Additional Anthropic API parameters

        Returns:
            ``Ok(AsyncIterator[StreamChunk])`` on successful setup.
            ``Err(LLMError)`` for recoverable connection failures.
        """
        try:
            # Extract system message if present
            system_msg = None
            conv_messages = []
            for msg in messages:
                if msg.role == Role.SYSTEM:
                    system_msg = msg.content
                else:
                    conv_messages.append(self._convert_message(msg))

            # Build thinking param; suppress temperature (incompatible with thinking)
            params = {
                "model": kwargs.pop("model", self.config.model),
                "messages": conv_messages,
                "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens or 1024),
                **kwargs,
            }
            self._apply_thinking(params)
            if "thinking" not in params:
                params["temperature"] = kwargs.pop(
                    "temperature", self.config.temperature
                )

            if system_msg:
                params["system"] = system_msg

            import asyncio

            stream_ctx = self.client.messages.stream(**params)
            if asyncio.iscoroutine(stream_ctx):
                stream_ctx = await stream_ctx

            return Ok(self._stream_impl(stream_ctx))

        except Exception as e:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(e)

    async def _stream_impl(self, stream_ctx: Any) -> AsyncGenerator[StreamChunk, None]:
        """Yield StreamChunk objects from an established Anthropic stream context.

        When ``thinking`` config is set on the config, uses the raw event
        stream to capture ``thinking_delta`` events alongside ``text_delta``
        events.  Otherwise falls back to the simpler ``text_stream`` path.
        """
        index = 0
        use_thinking = self.config.thinking is not None
        try:
            async with stream_ctx as stream:
                if use_thinking:
                    # Raw event iteration to capture thinking and text deltas
                    async for event in stream:
                        event_type = getattr(event, "type", None)
                        if event_type != "content_block_delta":
                            continue
                        delta = event.delta
                        delta_type = getattr(delta, "type", None)
                        if delta_type == "thinking_delta":
                            yield StreamChunk(
                                thinking_delta=getattr(delta, "thinking", None),
                                is_thinking=True,
                                model=self.config.model,
                                finish_reason=None,
                                index=index,
                            )
                            index += 1
                        elif delta_type == "text_delta":
                            yield StreamChunk(
                                delta=getattr(delta, "text", None),
                                is_thinking=False,
                                model=self.config.model,
                                finish_reason=None,
                                index=index,
                            )
                            index += 1
                else:
                    iter_source = getattr(stream, "text_stream", stream)
                    async for raw_text in iter_source:
                        text = (
                            raw_text.decode()
                            if isinstance(raw_text, bytes)
                            else raw_text
                        )
                        yield StreamChunk(
                            delta=text,
                            model=self.config.model,
                            finish_reason=None,
                            index=index,
                        )
                        index += 1
        except Exception as e:  # noqa: BLE001 — any stream failure is surfaced as a typed LLM error
            result = self._handle_error_as_result(e)
            if result.is_err():
                raise result.unwrap_err() from None
            raise AIError("Anthropic streaming failed") from None

    async def _do_chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolCall] | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate completion with Anthropic tool/function calling.

        Tool calling is handled by :meth:`_do_complete` via
        ``complete(..., tools=...)``; this method forwards the tool
        descriptors to keep the ``chat`` code path consistent.

        Args:
            messages: Chat messages.
            tools: Optional tool/function descriptors.
            **kwargs: Additional Anthropic API parameters.

        Returns:
            ``Ok(Completion)`` on success.  ``Err(LLMError)`` for recoverable
            failures.
        """
        return await self._do_complete(messages, tools=tools, **kwargs)

    def _apply_thinking(self, params: dict[str, Any]) -> None:
        """Inject Anthropic extended-thinking parameters into the API payload.

        When ``suppress`` is set, returns immediately — Anthropic's default is
        no thinking, so suppression simply means not injecting the parameter.

        Args:
            params: Mutable API payload dict.
        """
        if self.config.thinking is None:
            return
        if self.config.thinking.suppress:
            return
        params["thinking"] = {
            "type": "enabled",
            "budget_tokens": self.config.thinking.budget_tokens,
        }
        params.pop("temperature", None)

    def _convert_message(self, msg: ChatMessage) -> dict[str, Any]:
        """Convert ChatMessage to Anthropic format.

        Uses ``serialize_content_for_anthropic`` to convert multimodal message
        content to Anthropic-compatible block format. When ``thinking_blocks``
        is populated (multi-turn with extended thinking), prepends thinking blocks
        to the serialized content.

        Tool messages (``Role.TOOL``) become user turns with a ``tool_result``
        block; assistant turns that requested tools gain ``tool_use`` blocks so
        tool conversations round-trip correctly.

        Args:
            msg: ChatMessage to convert

        Returns:
            Anthropic message dict with ``role`` and ``content`` keys
        """
        if msg.role == Role.TOOL:
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id or "",
                        "content": _tool_result_text(msg.content),
                    }
                ],
            }

        role = "user" if msg.role == Role.USER else "assistant"
        tool_use_blocks: list[dict[str, Any]] = []
        for call in msg.tool_calls or []:
            if call.function is None:
                continue
            tool_use_blocks.append(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.function.name,
                    "input": parse_json_arguments(call.function.arguments),
                }
            )

        if msg.thinking_blocks:
            # Only include serialized_content if it's non-trivially empty
            # (empty string content produces [{"type": "text", "text": ""}] which Anthropic rejects)
            if msg.content in ("", []):
                content: list[dict[str, Any]] = list(msg.thinking_blocks)
            else:
                content = list(msg.thinking_blocks) + serialize_content_for_anthropic(
                    msg.content
                )
            if tool_use_blocks:
                content.extend(tool_use_blocks)
            return {"role": role, "content": content}

        if msg.content in ("", []):
            return {
                "role": role,
                "content": tool_use_blocks,
            }

        return {
            "role": role,
            "content": serialize_content_for_anthropic(msg.content) + tool_use_blocks,
        }

    def _handle_error_as_result(self, error: Exception) -> Result[Any, LLMError]:
        """Map a caught exception to ``Err`` (recoverable) or re-raise (infra)."""
        err_str = str(error).lower()
        if "authentication" in err_str or "api key" in err_str:
            raise LLMAuthenticationError("Anthropic authentication failed") from None
        if "rate limit" in err_str:
            return Err(LLMRateLimitError("Anthropic rate limit exceeded"))
        if "quota" in err_str or "billing" in err_str or "credit" in err_str:
            return Err(LLMQuotaExceededError("Anthropic quota exceeded"))
        if "content" in err_str and ("filter" in err_str or "policy" in err_str):
            return Err(LLMContentFilterError("Anthropic content filter"))
        if "model" in err_str and (
            "not found" in err_str or "does not exist" in err_str
        ):
            return Err(LLMModelNotFoundError("Anthropic model not found"))
        raise AIError("Anthropic infrastructure error") from None

    async def close(self) -> None:
        """Close the Anthropic client."""
        if getattr(self, "client", None) and not self._closed:
            await self.client.close()
        await super().close()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check.

        Returns:
            Structured health check result.
        """
        if self._closed:
            return HealthCheckResult(
                component="llm.anthropic",
                status=HealthStatus.UNHEALTHY,
                error="Client is closed",
            )

        return HealthCheckResult(
            component="llm.anthropic",
            status=HealthStatus.HEALTHY,
            details={
                "provider": "anthropic",
                "model": self.config.model,
            },
        )
