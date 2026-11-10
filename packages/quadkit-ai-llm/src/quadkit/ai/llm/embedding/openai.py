"""OpenAI embedding provider adapter."""

from __future__ import annotations

from quadkit.ai.llm.embedding._http_adapter import (
    _OpenAICompatEmbeddingAdapter,
)
from quadkit.ai.llm.embedding.base import EmbeddingModelInfo
from quadkit.ai.llm.embedding.config import OpenAIEmbeddingConfig


class OpenAIEmbeddingAdapter(_OpenAICompatEmbeddingAdapter):
    """Adapter for OpenAI embedding models.

    Talks to the real OpenAI ``/embeddings`` endpoint through
    :class:`~quadkit.ai.llm.http.client.ResilientHTTPClient`.
    """

    _provider = "openai"
    _api_key_env = "OPENAI_API_KEY"
    _default_model = "text-embedding-3-small"
    _default_base_url = "https://api.openai.com/v1"

    def __init__(self, config: OpenAIEmbeddingConfig) -> None:
        """Initialize OpenAI embedding adapter.

        Args:
            config: OpenAI embedding configuration.
        """
        super().__init__(config)

    def get_models(self) -> list[EmbeddingModelInfo]:
        """Get available OpenAI embedding models.

        Returns:
            List of model metadata
        """
        return [
            EmbeddingModelInfo(
                model_id="text-embedding-3-large",
                provider="openai",
                display_name="OpenAI Embedding 3 Large",
                embedding_dimension=3072,
                max_input_tokens=8191,
                input_cost_per_million=13.0,
            ),
            EmbeddingModelInfo(
                model_id="text-embedding-3-small",
                provider="openai",
                display_name="OpenAI Embedding 3 Small",
                embedding_dimension=1536,
                max_input_tokens=8191,
                input_cost_per_million=2.0,
            ),
        ]


__all__ = ["OpenAIEmbeddingAdapter"]
