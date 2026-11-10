"""Groq provider for ultra-fast LLM inference.

Groq provides blazing-fast inference speeds with their custom LPU (Language Processing Unit)
hardware, offering up to 10x faster token generation than traditional GPUs.

Supported Models:
- llama-3.1-405b-reasoning: Meta's largest Llama 3.1 model
- llama-3.1-70b-versatile: 70B parameter balanced model
- llama-3.1-8b-instant: Fast 8B parameter model
- mixtral-8x7b-32768: Mistral's MoE model with 32k context
- gemma-7b-it: Google's Gemma 7B instruction-tuned

Features:
- Ultra-fast inference (100+ tokens/second)
- Low latency (<1 second time-to-first-token)
- OpenAI-compatible API
- Function calling support
- Streaming support

Example:
    >>> from quadkit.ai.llm import GroqClient
    >>>
    >>> async with GroqClient(api_key="gsk_...") as client:
    ...     response = await client.complete(
    ...         model="llama-3.1-70b-versatile",
    ...         messages=[{"role": "user", "content": "Hello!"}]
    ...     )
    ...     print(response.content)

API Documentation: https://console.groq.com/docs

"""

from __future__ import annotations

from collections.abc import AsyncIterator
import types
from typing import Any, cast

import aiohttp

from quadkit.ai.llm.clients._message_utils import serialize_content_for_openai
from quadkit.ai.llm.clients._tools_utils import (
    parse_openai_tool_calls,
    serialize_message_for_openai,
    tool_to_openai_format,
)
from quadkit.ai.llm.clients.base import AbstractLLMClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMModelNotFoundError,
    LLMQuotaExceededError,
    LLMRateLimitError,
)
from quadkit.ai.llm.http.client import ResilientHTTPClient
from quadkit.ai.llm.types import (
    AIError,
    ChatMessage,
    Completion,
    StreamChunk,
    TokenUsage,
    ToolCall,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.logging import (
    get_logger,
    safe_error_type,
)
from quadkit.result import Err, Ok, Result
from quadkit.serialization import loads
from quadkit.validation import SecretStr

logger = get_logger(__name__)


class GroqClient(AbstractLLMClient):
    """Client for Groq's ultra-fast LLM inference API.

    Conforms to: :class:`~quadkit.contracts.ai.LLMClientProtocol` protocol via structural typing.

    Supports Chat, Stream, and Vision with:
    - Ultra-fast LPU hardware synergy
    - OpenAI-compatible API surface
    - Blazing-fast token generation
    """

    def __init__(self, config: ClientConfig):
        """Initialize Groq client.

        Args:
            config: LLM configuration
        """
        super().__init__(config=config)
        self._client: ResilientHTTPClient | None = None

    @property
    def api_key(self) -> SecretStr:
        """Get API key from config."""
        return self.config.api_key or SecretStr("")

    @property
    def base_url(self) -> str:
        """Get base URL from config."""
        return self.config.api_base or "https://api.groq.com/openai/v1"

    async def __aenter__(self) -> Any:
        """Async context manager entry."""
        self._client = ResilientHTTPClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            timeout=self.config.timeout,
            name="groq-client",
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Any:
        """Async context manager exit."""
        if self._client:
            await self._client.close()
            self._client = None

    def _get_client(self) -> ResilientHTTPClient:
        """Get or create HTTP client.

        Returns:
            HTTP client instance.
        """
        if self._client is None:
            self._client = ResilientHTTPClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
                name="groq-client",
            )
        return self._client

    async def _do_complete(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate chat completion.

        Args:
            model: Model ID (e.g., "llama-3.1-70b-versatile").
            messages: List of messages (ChatMessage or dict).
            temperature: Sampling temperature (0-2, default: 0.7).
            max_tokens: Maximum tokens to generate.
            stream: Whether to stream the response.
            tools: Function calling tools (OpenAI format).
            **kwargs: Additional parameters.

        Returns:
            ``Ok(Completion)`` for non-streaming success.
            ``Ok(AsyncIterator[StreamChunk])`` for streaming success.
            ``Err(LLMError)`` for recoverable failures.

        Raises:
            LLMAuthenticationError: If API key is invalid.
            AIError: For unexpected infrastructure failures.
        """
        try:
            client = self._get_client()
            model = kwargs.pop("model", self.config.model)
            temperature = kwargs.pop("temperature", self.config.temperature)
            max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)
            tools = kwargs.pop("tools", None)

            # Convert ChatMessage to dict
            message_dicts: list[dict[str, Any]] = []
            for msg in cast("list[ChatMessage | dict[str, Any]]", messages):
                if isinstance(msg, ChatMessage):
                    message_dicts.append(serialize_message_for_openai(msg))
                else:
                    message_dicts.append(msg)

            # Build request payload
            payload = {
                "model": model,
                "messages": message_dicts,
                "temperature": temperature,
                "stream": False,
                **kwargs,
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            if tools:
                payload["tools"] = [
                    converted
                    for tool in tools
                    if (converted := tool_to_openai_format(tool)) is not None
                ]

            # Non-streaming request
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json

            # Parse response
            choice = data["choices"][0]
            message = choice["message"]

            # Handle function calling
            tool_calls = parse_openai_tool_calls(message.get("tool_calls"))

            return Ok(
                Completion(
                    content=message.get("content", ""),
                    model=model,
                    finish_reason=choice.get("finish_reason", "stop"),
                    usage=TokenUsage(
                        prompt_tokens=data["usage"]["prompt_tokens"],
                        completion_tokens=data["usage"]["completion_tokens"],
                        total_tokens=data["usage"]["total_tokens"],
                    ),
                    tool_calls=tool_calls,
                )
            )
        except Exception as e:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(e)

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[AsyncIterator[StreamChunk], LLMError]:
        """Start a streaming completion (protocol-aligned method).

        Args:
            messages: List of chat messages (ChatMessage or dict).
            **kwargs: Additional Groq API parameters.

        Returns:
            ``Ok(AsyncIterator[StreamChunk])`` on success.
            ``Err(LLMError)`` for recoverable failures.
        """
        try:
            client = self._get_client()
            model = kwargs.pop("model", self.config.model)
            temperature = kwargs.pop("temperature", self.config.temperature)
            max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)

            # Convert ChatMessage to dict
            message_dicts: list[dict[str, Any]] = []
            for msg in cast("list[ChatMessage | dict[str, Any]]", messages):
                if isinstance(msg, ChatMessage):
                    message_dicts.append(
                        {
                            "role": msg.role.value,
                            "content": serialize_content_for_openai(msg.content),
                        }
                    )
                else:
                    message_dicts.append(msg)

            payload = {
                "model": model,
                "messages": message_dicts,
                "temperature": temperature,
                "stream": True,
                **kwargs,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens

            return Ok(self._stream_completion(client, payload))
        except Exception as e:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(e)

    async def _do_chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolCall] | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        return await self._do_complete(messages, tools=tools, **kwargs)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Run a lightweight provider health probe."""
        try:
            _ = await self.list_models()
            return HealthCheckResult(
                component="llm.groq",
                status=HealthStatus.HEALTHY,
                details={"model": self.config.model},
            )
        except Exception as exc:  # noqa: BLE001 — health probes must never raise — report unhealthy
            return HealthCheckResult(
                component="llm.groq",
                status=HealthStatus.UNHEALTHY,
                error=f"Provider health check failed ({type(exc).__name__})",
            )

    async def list_models(self) -> list[dict[str, Any]]:
        """List models available from the Groq API."""
        client = self._get_client()
        response = await client.get("/models")
        response.raise_for_status()
        data = response.json
        return cast("list[dict[str, Any]]", data.get("data", []))

    async def _stream_completion(
        self,
        client: ResilientHTTPClient,
        payload: dict[str, Any],
    ) -> AsyncIterator[StreamChunk]:
        """Stream chat completion.

        Args:
            client: HTTP client.
            payload: Request payload.

        Yields:
            StreamChunk objects.

        """
        try:
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or line == "data: [DONE]":
                        continue

                    if line.startswith("data: "):
                        try:
                            data = loads(line[6:].encode("utf-8"))
                            choice = data["choices"][0]
                            delta = choice.get("delta", {})

                            content = delta.get("content", "")
                            if content:
                                yield StreamChunk(
                                    delta=content,
                                    model=data["model"],
                                    finish_reason=choice.get("finish_reason"),
                                )

                        except (ValueError, TypeError) as e:
                            logger.debug(
                                "stream_chunk_parse_failed",
                                error_type=safe_error_type(e),
                            )
                            continue
        except Exception:
            raise AIError("Groq streaming failed") from None

    def _handle_error_as_result(self, error: Exception) -> Result[Any, LLMError]:
        """Map a caught exception to ``Err`` (recoverable) or re-raise (infra)."""
        if isinstance(error, aiohttp.ClientResponseError):
            if error.status == 401:
                raise LLMAuthenticationError("Groq authentication failed") from None
            if error.status == 429:
                return Err(LLMRateLimitError("Groq rate limit exceeded"))
            if error.status == 402:
                return Err(LLMQuotaExceededError("Groq quota exceeded"))
            if error.status == 404:
                return Err(LLMModelNotFoundError("Groq model not found"))
        raise AIError("Groq infrastructure error") from None

    async def close(self) -> None:
        """Close the HTTP client.

        Example:
            >>> await client.close()

        """
        if self._client:
            await self._client.close()
            self._client = None
        await super().close()


# Common model configurations for convenience
GROQ_MODELS = {
    "llama-3.1-405b-reasoning": {
        "context_window": 8192,
        "description": "Meta's largest Llama 3.1 model - best reasoning",
    },
    "llama-3.1-70b-versatile": {
        "context_window": 8192,
        "description": "Balanced 70B model - good for most tasks",
    },
    "llama-3.1-8b-instant": {
        "context_window": 8192,
        "description": "Fast 8B model - instant responses",
    },
    "mixtral-8x7b-32768": {
        "context_window": 32768,
        "description": "Mistral's MoE model - large context window",
    },
    "gemma-7b-it": {
        "context_window": 8192,
        "description": "Google's Gemma 7B - instruction tuned",
    },
}
