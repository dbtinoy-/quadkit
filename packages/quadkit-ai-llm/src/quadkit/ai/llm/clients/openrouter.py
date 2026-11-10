"""OpenRouter API client.

OpenRouter provides an OpenAI-compatible API surface. This client implements a
lightweight wrapper compatible with the existing OpenAI/OpenAICompatible clients
so it can be used interchangeably in higher-level code.
"""

from __future__ import annotations

import asyncio
import types
from typing import TYPE_CHECKING, Any, cast

import aiohttp

from quadkit.ai.llm.clients._tools_utils import (
    parse_openai_tool_calls,
    serialize_message_for_openai,
    tool_to_openai_format,
)
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMModelNotFoundError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from quadkit.ai.llm.http.client import ResilientHTTPClient
from quadkit.ai.llm.types import (
    AIError,
    ChatMessage,
    Completion,
    Role,
    StreamChunk,
    ThinkingResult,
    TokenUsage,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.web.http_models import HttpStatusError
from quadkit.logging import (
    get_logger,
    safe_error_type,
)
from quadkit.result import Err, Ok, Result
from quadkit.serialization import loads
from quadkit.validation import SecretStr

logger = get_logger(__name__)


from quadkit.ai.llm.clients.base import AbstractLLMClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.ai.llm.config import ClientConfig


class OpenRouterClient(AbstractLLMClient):
    """Client for OpenRouter (OpenAI-compatible) API.

    Conforms to: :class:`~quadkit.contracts.ai.LLMClientProtocol` protocol via structural typing.
    """

    def __init__(self, config: ClientConfig):
        """Initialize OpenRouter client.

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
        return self.config.api_base or "https://api.openrouter.ai/v1"

    @property
    def model(self) -> str:
        """Get default model from config."""
        return self.config.model

    async def _get_client(self) -> ResilientHTTPClient:
        """Get or create a resilient HTTP client for OpenRouter."""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            }
            self._client = ResilientHTTPClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.config.timeout,
                name="openrouter-client",
            )
        return self._client

    async def _do_complete(
        self,
        messages: list[Any],
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate chat completion.

        Accepts same message shape as other LLM clients used in the project.

        Returns:
            ``Ok(Completion)`` for non-streaming success.
            ``Ok(AsyncIterator[StreamChunk])`` for streaming success.
            ``Err(LLMError)`` for recoverable failures.
        """
        client = await self._get_client()
        temperature = kwargs.pop("temperature", self.config.temperature)
        max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)
        tools = kwargs.pop("tools", None)

        message_dicts: list[dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                message_dicts.append(serialize_message_for_openai(msg))
            else:
                message_dicts.append(msg)

        payload: dict[str, Any] = {
            "model": kwargs.pop("model", self.model),
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
        self._apply_thinking(payload)

        try:
            return Ok(await self._complete(client, payload))
        except Exception as e:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(e)

    async def _do_stream_chat(
        self,
        messages: list[Any],
        **kwargs: Any,
    ) -> Result[AsyncIterator[StreamChunk], LLMError]:
        """Start a streaming completion (protocol-aligned method).

        Args:
            messages: List of chat messages (ChatMessage or raw dicts).
            **kwargs: Additional OpenRouter API parameters.

        Returns:
            ``Ok(AsyncIterator[StreamChunk])`` on success.
            ``Err(LLMError)`` for recoverable failures.
        """
        try:
            client = await self._get_client()
            temperature = kwargs.pop("temperature", self.config.temperature)
            max_tokens = kwargs.pop("max_tokens", self.config.max_tokens)

            message_dicts: list[dict[str, Any]] = []
            for msg in messages:
                if isinstance(msg, ChatMessage):
                    message_dicts.append(
                        {"role": msg.role.value, "content": msg.content}
                    )
                else:
                    message_dicts.append(msg)

            payload: dict[str, Any] = {
                "model": kwargs.pop("model", self.model),
                "messages": message_dicts,
                "temperature": temperature,
                "stream": True,
                **kwargs,
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens
            self._apply_thinking(payload)

            return Ok(self._stream_completion(client, payload))
        except Exception as e:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(e)

    async def _do_chat(
        self,
        messages: list[Any],
        tools: list[Any] | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        return await self._do_complete(messages, tools=tools, **kwargs)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight health check against the OpenRouter API.

        Calls the models listing endpoint to verify the API key is valid and
        the service is reachable.

        Args:
            timeout: Maximum seconds to wait for the response.

        Returns:
            :class:`~quadkit.contracts.core.health.HealthCheckResult`.
        """
        try:
            client = await self._get_client()
            response = await client.get("/models")
            response.raise_for_status()
            return HealthCheckResult(
                component="llm.openrouter",
                status=HealthStatus.HEALTHY,
                details={"provider": "openrouter", "model": self.config.model},
            )
        except Exception as exc:  # noqa: BLE001 — health probes must never raise — report unhealthy
            return HealthCheckResult(
                component="llm.openrouter",
                status=HealthStatus.UNHEALTHY,
                error=f"Provider health check failed ({type(exc).__name__})",
            )

    async def _complete(
        self,
        client: ResilientHTTPClient,
        payload: dict[str, Any],
    ) -> Completion:
        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data: Any = response.json

            choice = data["choices"][0]
            message = choice["message"]

            tool_calls = parse_openai_tool_calls(message.get("tool_calls"))

            token_usage = None
            if "usage" in data:
                token_usage = TokenUsage(
                    prompt_tokens=data["usage"].get("prompt_tokens", 0),
                    completion_tokens=data["usage"].get("completion_tokens", 0),
                    total_tokens=data["usage"].get("total_tokens", 0),
                )

            # OpenRouter: reasoning field present when include_reasoning=True
            reasoning: str | None = message.get("reasoning") or None
            thinking: ThinkingResult | None = (
                ThinkingResult(content=reasoning) if reasoning else None
            )

            return Completion(
                content=message.get("content", ""),
                role=Role(message.get("role", "assistant")),
                tool_calls=tool_calls,
                finish_reason=choice.get("finish_reason"),
                usage=token_usage,
                thinking=thinking,
                model=data.get("model", self.model),
            )
        except (HttpStatusError, TimeoutError):
            # Propagate unchanged so _do_complete maps these to typed
            # LLMErrors via _handle_error_as_result (429 → rate limit,
            # timeout → LLMTimeoutError, etc.).
            raise
        except Exception:
            raise AIError("OpenRouter request failed") from None

    async def _stream_completion(
        self,
        client: ResilientHTTPClient,
        payload: dict[str, Any],
    ) -> AsyncIterator[StreamChunk]:
        try:
            stream_ctx = client.stream("POST", "/chat/completions", json=payload)
            if asyncio.iscoroutine(stream_ctx):
                stream_ctx = await stream_ctx

            async with stream_ctx as response:
                # Prefer content iteration when available, otherwise fall back
                # to aiohttp's line iterator for compatibility with various
                # underlying client implementations.
                if hasattr(response, "content"):
                    iterator = cast("AsyncIterator[bytes | str]", response.content)
                else:
                    iterator = cast(
                        "AsyncIterator[bytes | str]", response.aiter_lines()
                    )

                async for raw_line in iterator:
                    # aiter_lines() yields str; content iterators may yield bytes.
                    if isinstance(raw_line, bytes):
                        line = raw_line.decode("utf-8").strip()
                    else:
                        line = str(raw_line).strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = loads(data_str)
                        choice = data["choices"][0]
                        delta = choice.get("delta", {})
                        content = delta.get("content", "")
                        role = delta.get("role")
                        # OpenRouter: reasoning delta when include_reasoning=True
                        reasoning = delta.get("reasoning") or ""

                        if reasoning:
                            yield StreamChunk(
                                thinking_delta=reasoning,
                                is_thinking=True,
                                role=Role(role) if role else None,
                                finish_reason=choice.get("finish_reason"),
                                model=data.get("model", self.model),
                            )
                        elif content:
                            yield StreamChunk(
                                delta=content,
                                role=Role(role) if role else None,
                                finish_reason=choice.get("finish_reason"),
                                model=data.get("model", self.model),
                            )
                    except (ValueError, TypeError) as e:
                        logger.debug(
                            "openrouter_sse_parse_failed", error_type=safe_error_type(e)
                        )
                        continue
        except Exception:
            raise AIError("OpenRouter streaming failed") from None

    async def embeddings(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        client = await self._get_client()
        try:
            response = await client.post(
                "/embeddings",
                json={
                    "model": kwargs.pop("model", self.model),
                    "input": texts,
                    **kwargs,
                },
            )
            response.raise_for_status()
            data: Any = response.json
            embeddings = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
            return [item["embedding"] for item in embeddings]
        except Exception:
            raise AIError("OpenRouter request failed") from None

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
        await super().close()

    def _apply_thinking(self, payload: dict[str, Any]) -> None:
        """Inject OpenRouter reasoning parameters into the API payload.

        Sets ``include_reasoning = True`` when ``config.thinking`` is configured,
        which instructs OpenRouter to return the model's reasoning text in the
        ``reasoning`` field of the response message.

        Args:
            payload: Mutable API payload dict.
        """
        if self.config.thinking is not None:
            payload["include_reasoning"] = True

    def _handle_error_as_result(self, error: Exception) -> Result[Any, LLMError]:
        """Map a caught exception to ``Err`` (recoverable) or re-raise (infra).

        Handles both raw HTTP errors and already-converted AIError subclasses
        (since ``_complete()`` converts errors via ``_handle_error()`` before raising).
        """
        if isinstance(error, TimeoutError):
            return Err(
                LLMTimeoutError(
                    f"OpenRouter request timed out after {self.config.timeout}s"
                )
            )
        # Handle raw HTTP errors (e.g. from streaming setup)
        status = None
        if isinstance(error, (aiohttp.ClientResponseError, HttpStatusError)):
            status = error.status
        if status == 401:
            raise LLMAuthenticationError("OpenRouter authentication failed") from None
        if status == 429:
            return Err(LLMRateLimitError("OpenRouter rate limit exceeded"))
        if status == 402:
            return Err(LLMQuotaExceededError("OpenRouter quota exceeded"))
        if status == 404:
            return Err(LLMModelNotFoundError("OpenRouter model not found"))
        raise AIError("OpenRouter infrastructure error") from None

    async def __aenter__(self) -> Any:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Any:
        await self.close()
