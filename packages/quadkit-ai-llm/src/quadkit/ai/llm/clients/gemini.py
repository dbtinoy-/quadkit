"""Google Gemini REST API client for the Quadkit LLM routing system.

Implements the :class:`~quadkit.contracts.ai.protocols.LLMClientProtocol` protocol
against the ``generativelanguage.googleapis.com`` v1beta endpoint.

Key responsibilities:
* Translate OpenAI-compatible ``role``/``content`` messages into Gemini's
  ``contents[].parts`` format (including image ``inline_data`` parts).
* Map Gemini errors to the framework's typed exception hierarchy so the
  router can classify them without provider-specific logic.
* Return a normalised :class:`~quadkit.ai.llm.types.Completion` object.

Notes:
    Gemini does *not* expose an OpenAI-compatible endpoint — this client
    uses the native REST API directly via :class:`~quadkit.http.BaseURLHTTPClient`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
)
from quadkit.ai.llm.http.client import ResilientHTTPClient
from quadkit.ai.llm.types import (
    AIError,
    Completion,
    StreamChunk,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.web.http_models import HttpStatusError
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com"

from quadkit.ai.llm.clients.base import AbstractLLMClient
from quadkit.ai.llm.clients.gemini_helpers import (
    inject_thinking_config,
    messages_to_gemini,
    parse_gemini_response_with_tools,
    parse_gemini_sse_body,
    tool_to_gemini_function,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.ai.llm.config import ClientConfig

__all__ = ["GeminiClient", "_messages_to_gemini"]

_messages_to_gemini = messages_to_gemini


class GeminiClient(AbstractLLMClient):
    """Client for the Google Gemini REST API.

    Wraps ``generativelanguage.googleapis.com/v1beta/models/{model}:generateContent``
    and normalises the response to a standard :class:`~quadkit.ai.llm.types.Completion`.

    The Gemini API uses API-key query-parameter authentication, not Bearer
    tokens.  The key is read from ``ClientConfig.api_key`` and is never logged.

    Example:
        >>> config = ClientConfig(
        ...     provider="gemini",
        ...     model="gemini-2.5-flash",
        ...     api_key="AIza…",
        ...     timeout=60.0,
        ... )
        >>> client = GeminiClient(config)
        >>> completion = await client.complete(
        ...     messages=[{"role": "user", "content": "Describe quantum entanglement."}],
        ...     model="gemini-2.5-flash",
        ...     max_tokens=512,
        ... )
        >>> print(completion.content)
    """

    def __init__(self, config: ClientConfig) -> None:
        """Initialise the Gemini client.

        Args:
            config: LLM configuration.  ``config.api_key`` must be set;
                ``config.api_base`` overrides the default base URL when set.
        """
        super().__init__(config=config)
        self._http: ResilientHTTPClient | None = None

    @property
    def _api_key(self) -> str:
        """Return the raw API key string.

        Raises:
            LLMAuthenticationError: When ``config.api_key`` is not set.
        """
        key = self.config.api_key
        if key is None:
            msg = "GeminiClient requires api_key in ClientConfig"
            raise LLMAuthenticationError(msg)
        return key.get_secret_value()

    @property
    def _base_url(self) -> str:
        """Return the API base URL, using config override when provided."""
        return self.config.api_base or _BASE_URL

    def _get_http(self) -> ResilientHTTPClient:
        """Return a lazily-created HTTP client instance."""
        if self._http is None:
            self._http = ResilientHTTPClient(
                base_url=self._base_url,
                headers={"Content-Type": "application/json"},
                timeout=self.config.timeout,
                name="gemini-client",
            )
        return self._http

    # ──────────────────────────────────────────────────────────────────
    # LLMClientProtocol protocol implementation
    # ──────────────────────────────────────────────────────────────────

    async def _do_complete(  # type: ignore[override]
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate a completion from Gemini.

        Args:
            messages: OpenAI-compatible message list.
            model: Model identifier override.  When ``None``, uses
                ``config.model``.
            temperature: Sampling temperature (0.0–2.0).
            max_tokens: Maximum output tokens.
            **kwargs: Ignored for protocol compatibility.

        Returns:
            ``Ok(Completion)`` on success.  ``Err(LLMError)`` for recoverable
            failures (rate limit, quota, content filter, model not found).

        Raises:
            LLMAuthenticationError: When the API key is invalid (HTTP 401/403).
            AIError: For unexpected infrastructure failures.
        """
        active_model = model or self.config.model
        contents = messages_to_gemini(messages)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }
        if max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens
        inject_thinking_config(payload["generationConfig"], self.config)
        tools = kwargs.pop("tools", None)
        if tools:
            payload["tools"] = [
                {"functionDeclarations": [tool_to_gemini_function(t) for t in tools]}
            ]

        path = f"/v1beta/models/{active_model}:generateContent?key={self._api_key}"

        try:
            http = self._get_http()
            response = await http.post(path, json=payload)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(exc)

        data: dict[str, Any] = response.json
        try:
            return Ok(parse_gemini_response_with_tools(data, active_model))
        except AIError:
            return Err(
                LLMContentFilterError(
                    "gemini: response was blocked or contained no candidates"
                )
            )

    async def _do_stream_chat(
        self,
        messages: list[Any],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Result[AsyncIterator[StreamChunk], LLMError]:
        """Stream completion tokens from Gemini.

        Uses ``streamGenerateContent`` with SSE (``alt=sse``) to yield
        incremental text deltas as :class:`StreamChunk` objects.

        Args:
            messages: OpenAI-compatible message list.
            model: Model override.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            **kwargs: Ignored for protocol compatibility.

        Returns:
            ``Ok(AsyncIterator[StreamChunk])`` on successful connection.
            ``Err(LLMError)`` for recoverable failures.

        Raises:
            LLMAuthenticationError: When credentials are invalid.
            AIError: For unexpected infrastructure failures.
        """
        active_model = model or self.config.model
        contents = messages_to_gemini(messages)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens
        inject_thinking_config(payload["generationConfig"], self.config)

        path = (
            f"/v1beta/models/{active_model}:streamGenerateContent"
            f"?key={self._api_key}&alt=sse"
        )
        try:
            http = self._get_http()
            response = await http.post(path, json=payload)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(exc)

        # The non-streaming post returns the full SSE body as text;
        # parse newline-delimited JSON objects from the array.
        result = parse_gemini_sse_body(response.text or "", active_model)

        async def _to_async() -> AsyncIterator[StreamChunk]:
            for chunk in result:
                yield chunk

        return Ok(_to_async())

    async def _do_chat(  # type: ignore[override]
        self,
        messages: list[dict[str, Any]],
        tools: list[Any] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate completion with optional Gemini function calling.

        Tool calling is handled by :meth:`_do_complete` via
        ``complete(..., tools=...)``; this method forwards the tool
        descriptors to keep the ``chat`` code path consistent.

        Args:
            messages: OpenAI-compatible message list.
            tools: Optional tool/function descriptors.
            model: Model override.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            **kwargs: Ignored for protocol compatibility.

        Returns:
            ``Ok(Completion)`` on success.  ``Err(LLMError)`` for recoverable
            failures.
        """
        return await self._do_complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            **kwargs,
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight health check against the Gemini API.

        Attempts to list models — a zero-cost metadata call that verifies
        the API key is valid and the service is reachable.

        Args:
            timeout: Seconds to wait for the response (informational; the
                client-level timeout in ``config.timeout`` is used).

        Returns:
            :class:`~quadkit.contracts.core.health.HealthCheckResult`.
        """
        try:
            http = self._get_http()
            response = await http.get(
                f"/v1beta/models?key={self._api_key}&pageSize=1",
            )
            response.raise_for_status()
            return HealthCheckResult(component="gemini", status=HealthStatus.HEALTHY)
        except Exception as exc:  # noqa: BLE001 — health probes must never raise — report unhealthy
            return HealthCheckResult(
                component="gemini",
                status=HealthStatus.UNHEALTHY,
                error=f"Provider health check failed ({type(exc).__name__})",
            )

    def _handle_error_as_result(self, error: Exception) -> Result[Any, LLMError]:
        """Map a caught exception without exposing its message or URL."""
        status: int | None = None
        if isinstance(error, HttpStatusError):
            status = error.status

        if status in (401, 403):
            raise LLMAuthenticationError(
                f"gemini: authentication failed ({status})"
            ) from None
        if status == 429:
            return Err(LLMRateLimitError("gemini: rate limit exceeded"))
        if status == 400:
            if self._is_model_not_found_error(error):
                return Err(LLMModelNotFoundError("gemini: model not found"))
            return Err(LLMError("gemini: invalid request"))
        if status == 404:
            return Err(LLMModelNotFoundError("gemini: model not found"))
        raise AIError("gemini: infrastructure error") from None

    @staticmethod
    def _is_model_not_found_error(error: Exception) -> bool:
        """Classify provider response text without returning it to callers."""
        if not isinstance(error, HttpStatusError):
            return False
        response = error.response
        detail: object = None
        payload = response.json
        if isinstance(payload, dict):
            provider_error = payload.get("error")
            if isinstance(provider_error, dict):
                code = provider_error.get("status", provider_error.get("code"))
                if code in (404, "404", "NOT_FOUND", "MODEL_NOT_FOUND"):
                    return True
                detail = provider_error.get("message")
            elif isinstance(provider_error, str):
                detail = provider_error
            if detail is None:
                detail = payload.get("message")
        if not isinstance(detail, str):
            detail = response.text
        if not isinstance(detail, str):
            return False
        lowered = detail.casefold()
        return "not found" in lowered or "does not exist" in lowered

    async def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        if self._http is not None:
            await self._http.close()
            self._http = None
        await super().close()
