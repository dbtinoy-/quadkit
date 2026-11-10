"""Jina embedding provider adapter."""

from __future__ import annotations

from quadkit.ai.llm.embedding._http_adapter import (
    _OpenAICompatEmbeddingAdapter,
)
from quadkit.ai.llm.embedding.base import EmbeddingModelInfo
from quadkit.ai.llm.embedding.config import JinaEmbeddingConfig


class JinaEmbeddingAdapter(_OpenAICompatEmbeddingAdapter):
    """Adapter for Jina embedding models.

    Talks to the real Jina ``/embeddings`` endpoint (OpenAI-compatible
    shape) through
    :class:`~quadkit.ai.llm.http.client.ResilientHTTPClient`.
    """

    _provider = "jina"
    _api_key_env = "JINA_API_KEY"
    _default_model = "jina-embeddings-v3"
    _default_base_url = "https://api.jina.ai/v1"

    def __init__(self, config: JinaEmbeddingConfig) -> None:
        """Initialize Jina embedding adapter.

        Args:
            config: Jina embedding configuration.
        """
        super().__init__(config)

    def get_models(self) -> list[EmbeddingModelInfo]:
        """Get available Jina embedding models.

        Returns:
            List of model metadata
        """
        return [
            EmbeddingModelInfo(
                model_id="jina-embeddings-v3",
                provider="jina",
                display_name="Jina Embeddings v3",
                embedding_dimension=1024,
                max_input_tokens=8192,
                input_cost_per_million=0.02,
            ),
            EmbeddingModelInfo(
                model_id="jina-embeddings-v2-base-en",
                provider="jina",
                display_name="Jina Embeddings v2 Base",
                embedding_dimension=768,
                max_input_tokens=8192,
                input_cost_per_million=0.02,
            ),
        ]


__all__ = ["JinaEmbeddingAdapter"]
