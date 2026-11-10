"""Shared HTTP plumbing for embedding adapters.

Providers that expose an OpenAI-compatible ``/embeddings`` endpoint
(OpenAI, Jina, Voyage) are implemented once here; each adapter module
subclasses :class:`_OpenAICompatEmbeddingAdapter` with its endpoint
defaults and credential source.  All adapters talk to providers through
:class:`~quadkit.ai.llm.http.client.ResilientHTTPClient` and surface
failures as :class:`~quadkit.ai.llm.exceptions.EmbeddingError` (or the
specific auth/rate-limit classes for 401/403 and 429).
"""

from __future__ import annotations

import os
from typing import Any, ClassVar

from quadkit.ai.llm.embedding.base import AbstractEmbeddingAdapter
from quadkit.ai.llm.exceptions import (
    EmbeddingError,
    LLMAuthenticationError,
    LLMRateLimitError,
)
from quadkit.ai.llm.http.client import ResilientHTTPClient
from quadkit.contracts.core.health import (
    HealthCheckResult,
    HealthStatus,
)
from quadkit.contracts.web.http_models import HttpResponse
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


def raise_for_embedding_status(provider: str, response: HttpResponse) -> None:
    """Map a non-2xx HTTP status to the matching embedding error.

    Args:
        provider: Provider label for error messages.
        response: The HTTP response to inspect.

    Raises:
        LLMAuthenticationError: On 401/403.
        LLMRateLimitError: On 429.
        EmbeddingError: On any other 4xx/5xx status.
    """
    if response.status < 400:
        return
    status = response.status
    if status in (401, 403):
        raise LLMAuthenticationError(
            f"{provider} embedding authentication failed (HTTP {status})"
        )
    if status == 429:
        raise LLMRateLimitError(f"{provider} embedding rate limit exceeded (HTTP 429)")
    raise EmbeddingError(f"{provider} embedding request failed (HTTP {status})")


class _OpenAICompatEmbeddingAdapter(AbstractEmbeddingAdapter):
    """Base for adapters whose provider exposes an OpenAI-compatible API.

    The ``/embeddings`` request/response shape (``{"model", "input"}`` in,
    ``{"data": [{"index", "embedding"}]}`` out) is shared by OpenAI,
    Jina, and Voyage.

    Class attributes:
        _provider: Provider label for logs and error messages.
        _api_key_env: Environment variable holding the API key when the
            config does not set one explicitly.
    """

    _provider: ClassVar[str] = "openai"
    _api_key_env: ClassVar[str] = "OPENAI_API_KEY"
    _embed_path: ClassVar[str] = "/embeddings"
    _default_model: ClassVar[str] = "text-embedding-3-small"
    _default_base_url: ClassVar[str] = "https://api.openai.com/v1"
    _extra_headers: ClassVar[dict[str, str]] = {}
    _supports_dimensions: ClassVar[bool] = True

    def __init__(self, config: Any) -> None:
        """Initialize adapter from a provider-specific config dataclass."""
        super().__init__(config)
        self._api_key = getattr(config, "api_key", None)
        self._base_url = getattr(config, "base_url", None) or self._default_base_url
        self._client: ResilientHTTPClient | None = None

    def _resolve_api_key(self) -> str:
        """Return the configured key or fall back to the provider env var."""
        key = self._api_key or os.environ.get(self._api_key_env)
        if not key:
            msg = (
                f"{self._provider} API key not configured — set "
                f"{self._api_key_env} or pass api_key in the config"
            )
            raise EmbeddingError(msg)
        return key

    def _get_http_client(self) -> ResilientHTTPClient:
        """Return the lazily built HTTP client (tests patch this method)."""
        if self._client is None:
            self._client = ResilientHTTPClient(
                base_url=self._base_url,
                headers={**self._extra_headers},
                timeout=self._config.timeout,
                name=f"embedding-{self._provider}",
            )
        return self._client

    def _build_payload(self, model: str, batch: list[str]) -> dict[str, Any]:
        """Build the JSON body for one embedding batch."""
        payload: dict[str, Any] = {"model": model, "input": batch}
        if self._supports_dimensions and self._config.dimensions is not None:
            payload["dimensions"] = self._config.dimensions
        return payload

    async def embed(
        self,
        texts: str | list[str],
        *,
        model: str | None = None,
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings by posting batches to the provider API.

        Args:
            texts: Single text or list of texts.
            model: Model override (defaults to the provider default).
            batch_size: Number of texts per request.

        Returns:
            One embedding vector per input text, in input order.

        Raises:
            EmbeddingError: Missing key, HTTP failure, or malformed response.
        """
        model = model or self._default_model
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return []

        key = self._resolve_api_key()
        client = self._get_http_client()
        headers = {
            "Authorization": f"Bearer {key}",
            **self._extra_headers,
        }

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            logger.debug("embedding_batch", batch_size=len(batch))
            response = await client.post(
                self._embed_path,
                data=self._build_payload(model, batch),
                headers=headers,
            )
            raise_for_embedding_status(self._provider, response)
            embeddings.extend(self._extract_embeddings(response))
        return embeddings

    def _extract_embeddings(self, response: HttpResponse) -> list[list[float]]:
        """Parse one response body into ordered embedding vectors."""
        data = response.json
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            msg = f"{self._provider} embedding response missing 'data' list"
            raise EmbeddingError(msg)
        ordered = sorted(rows, key=lambda row: row.get("index", 0))
        vectors: list[list[float]] = []
        for row in ordered:
            vector = row.get("embedding") if isinstance(row, dict) else None
            if not isinstance(vector, list):
                msg = f"{self._provider} embedding response row missing 'embedding'"
                raise EmbeddingError(msg)
            vectors.append([float(value) for value in vector])
        return vectors

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Config-based health check (no network call).

        Returns HEALTHY when an API key is available, UNHEALTHY otherwise.
        The base-class default would issue a real embedding request, which
        is too expensive and billing-relevant for a health probe.
        """
        component = f"embedding_{self._provider}"
        if self._resolve_api_key_or_none():
            return HealthCheckResult(component=component, status=HealthStatus.HEALTHY)
        return HealthCheckResult(
            component=component,
            status=HealthStatus.UNHEALTHY,
            message="API key not configured",
        )

    def _resolve_api_key_or_none(self) -> str | None:
        """API key or None (health checks must not raise)."""
        return self._api_key or os.environ.get(self._api_key_env)

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._client is not None:
            await self._client.close()
            self._client = None
