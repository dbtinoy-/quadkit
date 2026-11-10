"""Voyage AI embedding provider adapter."""

from __future__ import annotations

from quadkit.ai.llm.embedding._http_adapter import (
    _OpenAICompatEmbeddingAdapter,
)
from quadkit.ai.llm.embedding.base import EmbeddingModelInfo
from quadkit.ai.llm.embedding.config import VoyageEmbeddingConfig


class VoyageEmbeddingAdapter(_OpenAICompatEmbeddingAdapter):
    """Adapter for Voyage embedding models.

    Talks to the real Voyage ``/embeddings`` endpoint (OpenAI-compatible
    shape) through
    :class:`~quadkit.ai.llm.http.client.ResilientHTTPClient`.
    """

    _provider = "voyage"
    _api_key_env = "VOYAGE_API_KEY"
    _default_model = "voyage-3"
    _default_base_url = "https://api.voyageai.com/v3"
    # Voyage dimensions are selected per model, not via a request field.
    _supports_dimensions = False

    def __init__(self, config: VoyageEmbeddingConfig) -> None:
        """Initialize Voyage embedding adapter.

        Args:
            config: Voyage embedding configuration.
        """
        super().__init__(config)

    def get_models(self) -> list[EmbeddingModelInfo]:
        """Get available Voyage embedding models.

        Returns:
            List of model metadata
        """
        return [
            EmbeddingModelInfo(
                model_id="voyage-3",
                provider="voyage",
                display_name="Voyage 3",
                embedding_dimension=1024,
                max_input_tokens=16000,
                input_cost_per_million=0.05,
            ),
            EmbeddingModelInfo(
                model_id="voyage-3-lite",
                provider="voyage",
                display_name="Voyage 3 Lite",
                embedding_dimension=512,
                max_input_tokens=16000,
                input_cost_per_million=0.02,
            ),
        ]


__all__ = ["VoyageEmbeddingAdapter"]
