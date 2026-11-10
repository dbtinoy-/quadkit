"""Mistral AI provider for European-based LLM inference.

Mistral AI is a European AI company providing high-performance LLMs with GDPR compliance
and data sovereignty guarantees. Their models excel at multilingual tasks and reasoning.

Supported Models:
- mistral-large-latest: Most capable model for complex tasks
- mistral-medium-latest: Balanced performance and cost
- mistral-small-latest: Fast, cost-effective model
- open-mixtral-8x22b: Large open-source MoE model
- open-mixtral-8x7b: Mid-size open-source MoE model
- open-mistral-7b: Compact open-source model

Features:
- GDPR compliant (EU-based)
- Strong multilingual support
- Function calling (select models)
- JSON mode for structured output
- Embeddings (mistral-embed)

Example:
    >>> from quadkit.ai.llm import MistralClient
    >>>
    >>> async with MistralClient(api_key="...") as client:
    ...     response = await client.complete(
    ...         model="mistral-large-latest",
    ...         messages=[{"role": "user", "content": "Bonjour!"}]
    ...     )
    ...     print(response.content)

API Documentation: https://docs.mistral.ai

"""

from __future__ import annotations

from collections.abc import AsyncIterator
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


class MistralClient(AbstractLLMClient):
    """Client for Mistral AI's LLM API.

    Conforms to: :class:`~quadkit.contracts.ai.LLMClientProtocol` protocol via structural typing.

    Supports Chat, Stream, and Embeddings with:
    - High-performance European LLMs
    - GDPR compliance and data sovereignty
    - Function calling and JSON mode
    """

    def __init__(self, config: ClientConfig):
        """Initialize Mistral client.

        Args:
            config: LLM configuration
        """
        super().__init__(config=config, max_retries=config.extra.get("max_retries", 3))
        self._client: ResilientHTTPClient | None = None

    @property
    def api_key(self) -> SecretStr:
        """Get API key from config."""
        return self.config.api_key or SecretStr("")

    @property
    def base_url(self) -> str:
        """Get base URL from config."""
        return self.config.api_base or "https://api.mistral.ai/v1"

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
                name="mistral-client",
            )
        return self._client

    async def _do_complete(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Provider-specific non-streaming completion.

        Args:
            messages: Chat messages (ChatMessage or dict).
            **kwargs: Forwarded kwargs (model, temperature, max_tokens, tools, response_format, etc.).

        Returns:
            ``Ok(Completion)`` on success or ``Err(LLMError)`` for recoverable failures.
        """
        try:
            client = self._get_client()
            model = kwargs.pop("model", self.config.model)
            temperature = kwargs.pop("temperature", self.config.temperature)
            max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)
            tools = kwargs.pop("tools", None)
            response_format = kwargs.pop("response_format", None)

            message_dicts: list[dict[str, Any]] = []
            for msg in cast("list[ChatMessage | dict[str, Any]]", messages):
                if isinstance(msg, ChatMessage):
                    message_dicts.append(serialize_message_for_openai(msg))
                else:
                    message_dicts.append(msg)

            payload: dict[str, Any] = {
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
            if response_format:
                payload["response_format"] = response_format

            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data: Any = response.json

            choice = data["choices"][0]
            message = choice["message"]

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
        """Provider-specific streaming implementation.

        Args:
            messages: Chat messages (ChatMessage or dict).
            **kwargs: Forwarded kwargs (model, temperature, max_tokens, tools, etc.).

        Returns:
            ``Ok(AsyncIterator[StreamChunk])`` on success or ``Err(LLMError)`` on failure.
        """
        try:
            client = self._get_client()
            model = kwargs.pop("model", self.config.model)
            temperature = kwargs.pop("temperature", self.config.temperature)
            max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)
            tools = kwargs.pop("tools", None)
            response_format = kwargs.pop("response_format", None)

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

            payload: dict[str, Any] = {
                "model": model,
                "messages": message_dicts,
                "temperature": temperature,
                "stream": True,
                **kwargs,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens
            if tools:
                payload["tools"] = tools
            if response_format:
                payload["response_format"] = response_format

            return Ok(self._stream_completion(client, payload))
        except Exception as e:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(e)

    async def _do_chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolCall] | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Provider-specific chat with tool support.

        Args:
            messages: Chat messages.
            tools: Optional tool definitions.
            **kwargs: Additional parameters.

        Returns:
            ``Ok(Completion)`` on success or ``Err(LLMError)`` on failure.
        """
        return await self._do_complete(messages, tools=tools, **kwargs)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight health check against the Mistral API.

        Calls the models endpoint to verify the API key is valid and the
        service is reachable.

        Args:
            timeout: Maximum seconds to wait for the response.

        Returns:
            :class:`~quadkit.contracts.core.health.HealthCheckResult`.
        """
        try:
            client = self._get_client()
            response = await client.get("/models")
            response.raise_for_status()
            return HealthCheckResult(
                component="llm.mistral",
                status=HealthStatus.HEALTHY,
                details={"provider": "mistral", "model": self.config.model},
            )
        except Exception as exc:  # noqa: BLE001 — health probes must never raise — report unhealthy
            return HealthCheckResult(
                component="llm.mistral",
                status=HealthStatus.UNHEALTHY,
                error=f"Provider health check failed ({type(exc).__name__})",
            )

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
            raise AIError("Mistral streaming failed") from None

    async def embed(
        self,
        model: str = "mistral-embed",
        input_texts: list[str] | str | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        """Generate embeddings.

        Args:
            model: Model ID (default: "mistral-embed").
            input_texts: Text or list of texts to embed.
            **kwargs: Additional parameters.

        Returns:
            List of embedding vectors.

        Example:
            >>> embeddings = await client.embed(
            ...     input_texts=["Hello world", "Bonjour monde"]
            ... )
            >>> print(f"Embedding dimension: {len(embeddings[0])}")

        """
        try:
            client = self._get_client()

            # Ensure input is list
            if isinstance(input_texts, str):
                input_texts = [input_texts]

            payload = {
                "model": model,
                "input": input_texts,
                **kwargs,
            }

            response = await client.post("/embeddings", json=payload)
            response.raise_for_status()
            data: Any = response.json

            # Extract embeddings
            return [item["embedding"] for item in data["data"]]
        except Exception:
            raise AIError("Mistral embedding request failed") from None

    def _handle_error_as_result(self, error: Exception) -> Result[Any, LLMError]:
        """Map a caught exception to ``Err`` (recoverable) or re-raise (infra)."""
        if isinstance(error, aiohttp.ClientResponseError):
            if error.status == 401:
                raise LLMAuthenticationError("Mistral authentication failed") from None
            if error.status == 429:
                return Err(LLMRateLimitError("Mistral rate limit exceeded"))
            if error.status == 402:
                return Err(LLMQuotaExceededError("Mistral quota exceeded"))
            if error.status == 404:
                return Err(LLMModelNotFoundError("Mistral model not found"))
        raise AIError("Mistral infrastructure error") from None

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
MISTRAL_MODELS = {
    "mistral-large-latest": {
        "context_window": 32000,
        "supports_tools": True,
        "description": "Most capable - complex reasoning and coding",
    },
    "mistral-medium-latest": {
        "context_window": 32000,
        "supports_tools": True,
        "description": "Balanced - good performance/cost ratio",
    },
    "mistral-small-latest": {
        "context_window": 32000,
        "supports_tools": True,
        "description": "Fast - cost-effective for simpler tasks",
    },
    "open-mixtral-8x22b": {
        "context_window": 64000,
        "supports_tools": True,
        "description": "Large open MoE - 64k context window",
    },
    "open-mixtral-8x7b": {
        "context_window": 32000,
        "supports_tools": False,
        "description": "Mid-size open MoE - good balance",
    },
    "open-mistral-7b": {
        "context_window": 32000,
        "supports_tools": False,
        "description": "Compact open model - fast inference",
    },
    "mistral-embed": {
        "context_window": None,
        "supports_tools": False,
        "description": "Embeddings model - 1024 dimensions",
    },
}
