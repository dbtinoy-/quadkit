"""Google Vertex AI LLM client for the Quadkit LLM routing system.

Implements the :class:`~quadkit.contracts.ai.protocols.LLMClientProtocol`
protocol against the Vertex AI ``predict`` REST endpoint using the
``google-auth`` library for service-account OAuth2 authentication.

The Vertex AI endpoint for Gemini models follows this pattern::

    https://{region}-aiplatform.googleapis.com/v1/projects/{project}/
        locations/{location}/publishers/google/models/{model}:generateContent

Configuration is sourced from ``ClientConfig.extra``:

* ``vertex_project``  — GCP project ID (required)
* ``vertex_location`` — Vertex location, e.g. ``us-central1`` (required)
* ``vertex_region``   — Region prefix for the hostname; defaults to
  ``vertex_location`` when omitted.
* ``vertex_credentials_file`` — Path to a service account JSON credentials
  file.  When absent, Application Default Credentials (ADC) are used.

Notes:
    ``google-auth`` and ``google-auth-httplib2`` are optional dependencies.
    An :class:`ImportError` is raised at construction time if they are absent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.llm.clients.base import AbstractLLMClient
from quadkit.ai.llm.clients.gemini_helpers import (
    inject_thinking_config,
    messages_to_gemini,
    parse_gemini_response_with_tools,
    parse_gemini_sse_body,
    tool_to_gemini_function,
)
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
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
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.web.http_models import HttpStatusError
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.ai.llm.config import ClientConfig

logger = get_logger(__name__)

__all__ = ["VertexAIClient"]

_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class VertexAIClient(AbstractLLMClient):
    """Google Vertex AI client using the native REST API.

    Authenticates via ``google-auth`` service-account credentials and routes
    requests to the Vertex AI ``generateContent`` endpoint.  All message and
    tool conversion reuses Gemini-native helpers because Vertex AI exposes the
    same Gemini model contract.

    Args:
        config: LLM configuration.  ``config.extra`` must contain
            ``vertex_project`` and ``vertex_location``.
    """

    def __init__(self, config: ClientConfig) -> None:
        """Initialise the Vertex AI client.

        Args:
            config: LLM configuration with Vertex-specific ``extra`` keys.

        Raises:
            ImportError: If ``google-auth`` is not installed.
            ValueError: If required ``extra`` keys are missing.
        """
        super().__init__(config=config)

        try:
            import google.auth  # noqa: F401
            import google.auth.transport.requests  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "VertexAIClient requires 'google-auth'. "
                "Install with: pip install google-cloud-aiplatform"
            ) from exc

        extra: dict[str, Any] = config.extra or {}
        self._project: str = extra.get("vertex_project", "")
        self._location: str = extra.get("vertex_location", "")
        self._region: str = extra.get("vertex_region", "") or self._location
        self._credentials_file: str | None = extra.get("vertex_credentials_file")

        if not self._project:
            raise ValueError(
                "VertexAIClient requires 'vertex_project' in ClientConfig.extra"
            )
        if not self._location:
            raise ValueError(
                "VertexAIClient requires 'vertex_location' in ClientConfig.extra"
            )

        self._http: ResilientHTTPClient | None = None
        self._access_token: str | None = None

    # ──────────────────────────────────────────────────────────────────
    # Token acquisition
    # ──────────────────────────────────────────────────────────────────

    async def _get_access_token(self) -> str:
        """Return a valid OAuth2 access token, refreshing when expired.

        Returns:
            Bearer token string.

        Raises:
            AIError: On credential failure.
        """
        import google.auth
        import google.auth.transport.requests

        try:
            if self._credentials_file:
                from google.oauth2 import (
                    service_account,
                )

                creds = service_account.Credentials.from_service_account_file(
                    self._credentials_file, scopes=[_SCOPE]
                )
            else:
                creds, _ = google.auth.default(scopes=[_SCOPE])

            req = google.auth.transport.requests.Request()
            if not creds.valid:
                creds.refresh(req)
            return cast("str", creds.token)
        except Exception:
            raise AIError("vertex: failed to acquire access token") from None

    # ──────────────────────────────────────────────────────────────────
    # HTTP client
    # ──────────────────────────────────────────────────────────────────

    async def _get_http(self) -> ResilientHTTPClient:
        """Return a lazily-created, token-refreshed HTTP client."""
        token = await self._get_access_token()
        base_url = f"https://{self._region}-aiplatform.googleapis.com"
        if self._http is None:
            self._http = ResilientHTTPClient(
                base_url=base_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
                name="vertex-ai-client",
            )
        else:
            # Refresh token header in-place
            self._http.headers["Authorization"] = f"Bearer {token}"
        return self._http

    def _model_path(self, model: str) -> str:
        """Build the Vertex AI model resource path.

        Args:
            model: Model ID, e.g. ``gemini-1.5-pro``.

        Returns:
            Full resource path string.
        """
        return (
            f"/v1/projects/{self._project}/locations/{self._location}"
            f"/publishers/google/models/{model}"
        )

    # ──────────────────────────────────────────────────────────────────
    # LLMClientProtocol implementation
    # ──────────────────────────────────────────────────────────────────

    async def _do_complete(
        self,
        messages: list[Any],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate a completion from Vertex AI.

        Args:
            messages: OpenAI-compatible message list.
            model: Model override.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            **kwargs: Ignored for protocol compatibility.

        Returns:
            ``Ok(Completion)`` on success.  ``Err(LLMError)`` for recoverable
            failures.

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
        tools = kwargs.pop("tools", None)
        if tools:
            payload["tools"] = [
                {"functionDeclarations": [tool_to_gemini_function(t) for t in tools]}
            ]

        path = f"{self._model_path(active_model)}:generateContent"
        try:
            http = await self._get_http()
            response = await http.post(path, json=payload)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(exc)

        return Ok(parse_gemini_response_with_tools(response.json, active_model))

    async def _do_stream_chat(
        self,
        messages: list[Any],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Result[AsyncIterator[StreamChunk], LLMError]:
        """Stream completion tokens from Vertex AI.

        Args:
            messages: OpenAI-compatible message list.
            model: Model override.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            **kwargs: Ignored for protocol compatibility.

        Returns:
            ``Ok(AsyncIterator[StreamChunk])`` on success.
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

        path = f"{self._model_path(active_model)}:streamGenerateContent?alt=sse"
        try:
            http = await self._get_http()
            response = await http.post(path, json=payload)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — any LLM client failure becomes an Err result, never a raw raise
            return self._handle_error_as_result(exc)

        result = parse_gemini_sse_body(response.text or "", active_model)

        async def _to_async() -> AsyncIterator[StreamChunk]:
            for chunk in result:
                yield chunk

        return Ok(_to_async())

    async def _do_chat(
        self,
        messages: list[Any],
        tools: list[Any] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate completion with optional tool calling on Vertex AI.

        Tool calling is handled by :meth:`_do_complete` via
        ``complete(..., tools=...)``; this method forwards the tool
        descriptors to keep the ``chat`` code path consistent.

        Args:
            messages: OpenAI-compatible message list.
            tools: Optional tool descriptors.
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
        """Probe Vertex AI with a minimal generateContent request.

        Args:
            timeout: Informational only.

        Returns:
            Structured :class:`~quadkit.contracts.core.health.HealthCheckResult`.
        """
        try:
            http = await self._get_http()
            path = (
                f"/v1/projects/{self._project}/locations/{self._location}"
                "/publishers/google/models"
            )
            resp = await http.get(path)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - transport/auth SDK stack varies
            return HealthCheckResult(
                component="llm.vertex_ai",
                status=HealthStatus.UNHEALTHY,
                error=f"Provider health check failed ({type(exc).__name__})",
            )

        return HealthCheckResult(
            component="llm.vertex_ai",
            status=HealthStatus.HEALTHY,
            details={
                "project": self._project,
                "location": self._location,
                "model": self.config.model,
            },
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http is not None:
            await self._http.close()
            self._http = None
        await super().close()

    def _handle_error_as_result(self, error: Exception) -> Result[Any, LLMError]:
        """Map a caught exception to ``Err`` or re-raise for infrastructure failures."""
        status: int | None = None
        if isinstance(error, HttpStatusError):
            status = error.status

        if status in (401, 403):
            raise LLMAuthenticationError(
                f"vertex: authentication failed ({status})"
            ) from None
        if status == 429:
            return Err(LLMRateLimitError("vertex: rate limit exceeded"))
        if status == 404:
            return Err(LLMModelNotFoundError("vertex: model not found"))
        raise AIError("vertex: infrastructure error") from None
