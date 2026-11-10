"""Local embedding provider adapter using sentence-transformers."""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.ai.llm.embedding.base import (
    AbstractEmbeddingAdapter,
    EmbeddingModelInfo,
)
from quadkit.ai.llm.embedding.config import LocalEmbeddingConfig
from quadkit.ai.llm.exceptions import EmbeddingError
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.logging import get_logger, safe_error_type

logger = get_logger(__name__)


class LocalEmbeddingAdapter(AbstractEmbeddingAdapter):
    """Adapter for local embedding models via sentence-transformers.

    Supports running embedding models locally for privacy-sensitive
    applications or when API access is restricted.  The
    ``sentence-transformers`` dependency is loaded lazily on first use so
    the adapter can be registered without the (heavy) dependency
    installed.
    """

    def __init__(self, config: LocalEmbeddingConfig) -> None:
        """Initialize local embedding adapter.

        Args:
            config: Local embedding configuration.
        """
        super().__init__(config)
        self._model_name = config.model
        self._device = config.device
        self._cache_dir = config.cache_dir
        self._model: Any = None

    def _load_model(self) -> Any:
        """Load (and cache) the sentence-transformers model.

        Raises:
            EmbeddingError: When sentence-transformers is not installed.
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                msg = (
                    "sentence-transformers is not installed — install it "
                    "(pip install sentence-transformers) to use the local "
                    "embedding adapter"
                )
                raise EmbeddingError(msg) from exc
            logger.debug("loading_local_embedding_model", device=self._device)
            self._model = SentenceTransformer(
                self._model_name,
                device=self._device,
                cache_folder=self._cache_dir,
            )
        return self._model

    async def embed(
        self,
        texts: str | list[str],
        *,
        model: str | None = None,
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings locally.

        Args:
            texts: Text(s) to embed.
            model: Model override (ignored, uses configured model).
            batch_size: Batch size for processing.

        Returns:
            List of embedding vectors.

        Raises:
            EmbeddingError: When the model cannot be loaded.
        """
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return []

        logger.debug(
            "embedding_local",
            device=self._device,
            text_count=len(texts),
        )

        st_model = await asyncio.to_thread(self._load_model)
        vectors = await asyncio.to_thread(st_model.encode, texts, batch_size=batch_size)
        return [[float(value) for value in vector] for vector in vectors]

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check if the model can be loaded.

        Loads the model (cached after first load) to verify the local
        stack works.

        Args:
            timeout: Check timeout (seconds).

        Returns:
            HealthCheckResult indicating HEALTHY if the model loads.
        """
        component = "embedding_local"
        try:
            await asyncio.to_thread(self._load_model)
            return HealthCheckResult(component=component, status=HealthStatus.HEALTHY)
        except Exception as exc:  # noqa: BLE001 — health probe reports any failure
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Embedding health check failed ({safe_error_type(exc)})",
            )

    def get_models(self) -> list[EmbeddingModelInfo]:
        """Get available local embedding models.

        Returns:
            List of model metadata
        """
        return [
            EmbeddingModelInfo(
                model_id="all-MiniLM-L6-v2",
                provider="local",
                display_name="All MiniLM L6 v2",
                embedding_dimension=384,
                max_input_tokens=256,
                input_cost_per_million=0.0,  # Free - local
            ),
            EmbeddingModelInfo(
                model_id="all-mpnet-base-v2",
                provider="local",
                display_name="All MPNet Base v2",
                embedding_dimension=768,
                max_input_tokens=384,
                input_cost_per_million=0.0,
            ),
            EmbeddingModelInfo(
                model_id="multilingual-e5-large",
                provider="local",
                display_name="Multilingual E5 Large",
                embedding_dimension=1024,
                max_input_tokens=512,
                input_cost_per_million=0.0,
            ),
            EmbeddingModelInfo(
                model_id="bge-large-zh-v1.5",
                provider="local",
                display_name="BGE Large ZH v1.5",
                embedding_dimension=1024,
                max_input_tokens=512,
                input_cost_per_million=0.0,
            ),
        ]

    async def close(self) -> None:
        """Clean up resources."""
        self._model = None


__all__ = ["LocalEmbeddingAdapter"]
