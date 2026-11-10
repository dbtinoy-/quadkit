"""Cohere embedding provider adapter."""

from __future__ import annotations

import os
from typing import Any

from quadkit.ai.llm.embedding._http_adapter import raise_for_embedding_status
from quadkit.ai.llm.embedding.base import (
    AbstractEmbeddingAdapter,
    EmbeddingModelInfo,
)
from quadkit.ai.llm.embedding.config import CohereEmbeddingConfig
from quadkit.ai.llm.exceptions import EmbeddingError
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


class CohereEmbeddingAdapter(AbstractEmbeddingAdapter):
    """Adapter for Cohere embedding models.

    Talks to the real Cohere v2 ``/embed`` endpoint through
    :class:`~quadkit.ai.llm.http.client.ResilientHTTPClient`.
    """

    _api_key_env = "COHERE_API_KEY"

    def __init__(self, config: CohereEmbeddingConfig) -> None:
        """Initialize Cohere embedding adapter.

        Args:
            config: Cohere embedding configuration.
        """
        super().__init__(config)
        self._api_key = config.api_key
        self._base_url = config.base_url
        self._input_type = config.input_type
        self._client: ResilientHTTPClient | None = None

    def _resolve_api_key(self) -> str:
        """Return the configured key or fall back to COHERE_API_KEY."""
        key = self._api_key or os.environ.get(self._api_key_env)
        if not key:
            msg = (
                "Cohere API key not configured — set COHERE_API_KEY or "
                "pass api_key in the config"
            )
            raise EmbeddingError(msg)
        return key

    def _get_http_client(self) -> ResilientHTTPClient:
        """Return the lazily built HTTP client (tests patch this method)."""
        if self._client is None:
            self._client = ResilientHTTPClient(
                base_url=self._base_url,
                timeout=self._config.timeout,
                name="embedding-cohere",
            )
        return self._client

    async def embed(
        self,
        texts: str | list[str],
        *,
        model: str | None = None,
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings using the Cohere v2 API.

        Args:
            texts: Text(s) to embed.
            model: Model to use (default: embed-english-v3.0).
            batch_size: Batch size for processing.

        Returns:
            List of embedding vectors (one per input text).

        Raises:
            EmbeddingError: Missing key, HTTP failure, or malformed response.
        """
        model = model or self._config.model or "embed-english-v3.0"
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return []

        key = self._resolve_api_key()
        client = self._get_http_client()
        headers = {"Authorization": f"Bearer {key}"}

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            logger.debug("embedding_batch", batch_size=len(batch))
            payload: dict[str, Any] = {
                "model": model,
                "texts": batch,
                "input_type": self._input_type,
            }
            response = await client.post("/v2/embed", data=payload, headers=headers)
            raise_for_embedding_status("cohere", response)
            embeddings.extend(self._extract_embeddings(response))
        return embeddings

    def _extract_embeddings(self, response: HttpResponse) -> list[list[float]]:
        """Parse one Cohere response body into embedding vectors."""
        data = response.json
        vectors = data.get("embeddings") if isinstance(data, dict) else None
        if not isinstance(vectors, list):
            msg = "Cohere embedding response missing 'embeddings' list"
            raise EmbeddingError(msg)
        return [[float(value) for value in vector] for vector in vectors]

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Config-based health check (no network call).

        Returns:
            HealthCheckResult indicating HEALTHY if API key is configured.
        """
        component = "embedding_cohere"
        if self._api_key or os.environ.get(self._api_key_env):
            return HealthCheckResult(component=component, status=HealthStatus.HEALTHY)
        return HealthCheckResult(
            component=component,
            status=HealthStatus.UNHEALTHY,
            message="API key not configured",
        )

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    def get_models(self) -> list[EmbeddingModelInfo]:
        """Get available Cohere embedding models.

        Returns:
            List of model metadata
        """
        return [
            EmbeddingModelInfo(
                model_id="embed-english-v3.0",
                provider="cohere",
                display_name="Cohere Embed English v3",
                embedding_dimension=1024,
                max_input_tokens=512,
                input_cost_per_million=0.1,
            ),
            EmbeddingModelInfo(
                model_id="embed-multilingual-v3.0",
                provider="cohere",
                display_name="Cohere Embed Multilingual v3",
                embedding_dimension=1024,
                max_input_tokens=512,
                input_cost_per_million=0.1,
            ),
        ]


__all__ = ["CohereEmbeddingAdapter"]
