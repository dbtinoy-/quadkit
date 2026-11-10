"""Central registry for embedding providers and models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.ai.llm.embedding.base import (
        AbstractEmbeddingAdapter,
        EmbeddingModelInfo,
    )

logger = get_logger(__name__)


class EmbeddingProviderRegistry:
    """Central registry for embedding providers and models.

    Manages registration and lookup of embedding adapters and their models.
    Providers (or tests) must register adapters explicitly via register_provider().
    """

    def __init__(self) -> None:
        """Initialize embedding provider registry."""
        self._providers: dict[str, AbstractEmbeddingAdapter] = {}
        self._models: dict[str, EmbeddingModelInfo] = {}
        self._provider_models: dict[str, list[str]] = {}

    def register_provider(
        self,
        provider_name: str,
        adapter: AbstractEmbeddingAdapter,
        models: list[EmbeddingModelInfo] | None = None,
    ) -> None:
        """Register an embedding provider.

        Args:
            provider_name: Provider identifier.
            adapter: The embedding adapter instance.
            models: Optional list of available models; falls back to adapter.get_models().
        """
        self._providers[provider_name] = adapter
        self._provider_models[provider_name] = []

        models_to_register = models if models is not None else adapter.get_models()
        for model in models_to_register:
            self._models[model.model_id] = model
            self._provider_models[provider_name].append(model.model_id)

    def get_adapter(self, provider_name: str) -> AbstractEmbeddingAdapter | None:
        """Get adapter for a provider.

        Args:
            provider_name: Provider name.

        Returns:
            Adapter instance if found, None otherwise.
        """
        return self._providers.get(provider_name)

    def get_adapter_for_model(self, model_id: str) -> AbstractEmbeddingAdapter | None:
        """Get adapter for a specific model.

        Args:
            model_id: Model identifier.

        Returns:
            Adapter instance if found, None otherwise.
        """
        model_info = self._models.get(model_id)
        if model_info:
            return self._providers.get(model_info.provider)
        return None

    def get_model_info(self, model_id: str) -> EmbeddingModelInfo | None:
        """Get metadata for a model.

        Args:
            model_id: Model identifier.

        Returns:
            Model metadata if found, None otherwise.
        """
        return self._models.get(model_id)

    def list_providers(self) -> list[str]:
        """List all registered providers.

        Returns:
            Provider names.
        """
        return list(self._providers.keys())

    def list_models(
        self,
        provider: str | None = None,
        embedding_dimension: int | None = None,
    ) -> list[EmbeddingModelInfo]:
        """List available embedding models.

        Args:
            provider: Optional provider filter.
            embedding_dimension: Optional output-dimension filter.

        Returns:
            List of model metadata.
        """
        models = list(self._models.values())
        if provider:
            model_ids = self._provider_models.get(provider, [])
            models = [m for m in models if m.model_id in model_ids]
        if embedding_dimension is not None:
            models = [m for m in models if m.embedding_dimension == embedding_dimension]
        return models

    async def close_all(self) -> None:
        """Close all provider connections."""
        for adapter in self._providers.values():
            await adapter.close()


def register_default_embedding_adapters(
    registry: EmbeddingProviderRegistry,
) -> None:
    """Register the built-in embedding adapters into *registry*."""
    from quadkit.ai.llm.embedding.cohere import CohereEmbeddingAdapter
    from quadkit.ai.llm.embedding.config import (
        CohereEmbeddingConfig,
        JinaEmbeddingConfig,
        LocalEmbeddingConfig,
        OpenAIEmbeddingConfig,
        VoyageEmbeddingConfig,
    )
    from quadkit.ai.llm.embedding.jina import JinaEmbeddingAdapter
    from quadkit.ai.llm.embedding.local import LocalEmbeddingAdapter
    from quadkit.ai.llm.embedding.openai import OpenAIEmbeddingAdapter
    from quadkit.ai.llm.embedding.voyage import VoyageEmbeddingAdapter

    defaults: list[tuple[str, AbstractEmbeddingAdapter]] = [
        ("openai", OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig())),
        ("cohere", CohereEmbeddingAdapter(CohereEmbeddingConfig())),
        ("voyage", VoyageEmbeddingAdapter(VoyageEmbeddingConfig())),
        ("jina", JinaEmbeddingAdapter(JinaEmbeddingConfig())),
        ("local", LocalEmbeddingAdapter(LocalEmbeddingConfig())),
    ]
    for name, adapter in defaults:
        registry.register_provider(name, adapter)


__all__ = ["EmbeddingProviderRegistry", "register_default_embedding_adapters"]
