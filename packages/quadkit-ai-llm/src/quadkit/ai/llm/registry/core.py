"""Provider registry for LLM clients.

This module provides a registry for discovering and managing LLM providers,
making it easy to add custom providers and query available options.

Example:
    >>> from quadkit.ai.llm.registry.core import ProviderRegistry
    >>> from quadkit.di.container import Container
    >>>
    >>> # Resolve via the DI container (recommended)
    >>> container = Container()
    >>> registry = await container.resolve(ProviderRegistry)
    >>>
    >>> # Get built-in provider
    >>> info = registry.get_provider("openai")
    >>> print(f"Models: {info.default_models}")
    >>>
    >>> # Register custom provider
    >>> from my_package import CustomLLMClient
    >>> registry.register(
    ...     name="custom",
    ...     client_class=CustomLLMClient,
    ...     default_models=["custom-gpt-1"],
    ...     supports_streaming=True
    ... )

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.ai import LLMClientProtocol
    from quadkit.contracts.ai.providers import ModelInfo
    from quadkit.contracts.ai.types import ModelCapability

from quadkit.logging import (
    get_logger,
)
from quadkit.primitives.registry import Registry

logger = get_logger(__name__)


__all__ = [
    "ProviderInfo",
    "ProviderRegistry",
]


@dataclass
class ProviderInfo:
    """Information about an LLM provider.

    Attributes:
        name: Provider identifier (e.g., "openai", "anthropic").
        client_class: LLMClientProtocol implementation class.
        default_models: List of default/recommended models.
        supports_streaming: Whether streaming is supported.
        supports_tools: Whether function/tool calling is supported.
        supports_vision: Whether vision/image inputs are supported.
        base_url: Default base URL for API (optional).
        docs_url: Documentation URL (optional).
        pricing_url: Pricing page URL (optional).
        description: Human-readable description.

    """

    name: str
    # Concrete provider implementations are stored as classes for metadata and
    # instantiation. Structural protocol conformance is enforced on instances.
    client_class: type[object]
    default_models: list[str] = field(default_factory=list)
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_vision: bool = False
    base_url: str | None = None
    docs_url: str | None = None
    pricing_url: str | None = None
    description: str = ""


class ProviderRegistry(Registry[str, ProviderInfo]):
    """Registry for LLM providers.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-in catalogue or :meth:`register` for custom providers.
    """

    def __init__(self) -> None:
        """Initialize an empty provider registry."""
        super().__init__(name="providers")
        self._provider_clients: dict[str, LLMClientProtocol] = {}
        self._provider_models: dict[str, list[ModelInfo]] = {}

    @staticmethod
    def _validate_provider_name(name: str) -> None:
        """Validate a provider registry key."""
        if not name or " " in name or name != name.lower():
            msg = "Provider name must be lowercase with no spaces (e.g., 'my-provider')"
            raise ValueError(msg)

    @classmethod
    def _default_entries(cls) -> dict[str, ProviderInfo]:
        """The complete in-package built-in set, declared exactly once.

        The catalogue lives in :mod:`quadkit.ai.llm.registry.builtins`;
        each client module is imported lazily inside
        :func:`~quadkit.ai.llm.registry.builtins.builtin_provider_entries`
        so SDK imports stay deferred until a registry is populated.
        """
        from quadkit.ai.llm.registry.builtins import builtin_provider_entries

        entries: dict[str, ProviderInfo] = {}
        for raw in builtin_provider_entries():
            info = ProviderInfo(**raw)
            entries[info.name] = info
        return entries

    @classmethod
    def with_defaults(cls) -> ProviderRegistry:
        """Return an instance populated with the built-in providers."""
        registry = cls()
        for info in cls._default_entries().values():
            registry.register(
                info.name,
                info.client_class,
                default_models=info.default_models,
                supports_streaming=info.supports_streaming,
                supports_tools=info.supports_tools,
                supports_vision=info.supports_vision,
                base_url=info.base_url,
                docs_url=info.docs_url,
                pricing_url=info.pricing_url,
                description=info.description,
            )
        logger.info("Initialized %d built-in providers", len(registry))
        return registry

    def register(  # type: ignore[override]
        self,
        name: str,
        client_class: type[object],
        default_models: list[str] | None = None,
        supports_streaming: bool = True,
        supports_tools: bool = False,
        supports_vision: bool = False,
        base_url: str | None = None,
        docs_url: str | None = None,
        pricing_url: str | None = None,
        description: str = "",
    ) -> ProviderInfo:
        """Register a new LLM provider."""
        self._validate_provider_name(name)

        info = ProviderInfo(
            name=name,
            client_class=client_class,
            default_models=default_models or [],
            supports_streaming=supports_streaming,
            supports_tools=supports_tools,
            supports_vision=supports_vision,
            base_url=base_url,
            docs_url=docs_url,
            pricing_url=pricing_url,
            description=description,
        )
        return super().register(name, info)

    def get_provider(self, name: str) -> ProviderInfo:
        """Get provider information."""
        info = super().get(name)
        if info is None:
            available = ", ".join(self.list_providers())
            msg = f"Provider '{name}' not found. Available providers: {available}"
            raise KeyError(msg)

        return info

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return sorted(super().keys())

    def search_providers(
        self,
        supports_streaming: bool | None = None,
        supports_tools: bool | None = None,
        supports_vision: bool | None = None,
    ) -> list[ProviderInfo]:
        """Search providers by capabilities."""
        results = []

        for info in self.values():
            if (
                supports_streaming is not None
                and info.supports_streaming != supports_streaming
            ):
                continue
            if supports_tools is not None and info.supports_tools != supports_tools:
                continue
            if supports_vision is not None and info.supports_vision != supports_vision:
                continue

            results.append(info)

        return results

    def unregister(self, name: str) -> None:
        """Unregister a provider."""
        self._provider_clients.pop(name, None)
        self._provider_models.pop(name, None)
        if super().unregister(name) is None:
            msg = f"Provider '{name}' not found"
            raise KeyError(msg)

    # --- Protocol Implementation ---

    async def register_provider(
        self, name: str, client: LLMClientProtocol, models: list[ModelInfo]
    ) -> None:
        """Register a provider following the ProviderRegistryProtocol."""
        from quadkit.contracts.ai.types import ModelCapability

        self._validate_provider_name(name)

        existing = super().get(name)
        supports_streaming = (
            any(ModelCapability.STREAMING in model.capabilities for model in models)
            if models
            else (existing.supports_streaming if existing is not None else True)
        )
        supports_tools = (
            any(
                ModelCapability.FUNCTION_CALLING in model.capabilities
                for model in models
            )
            if models
            else (existing.supports_tools if existing is not None else False)
        )
        supports_vision = (
            any(ModelCapability.VISION in model.capabilities for model in models)
            if models
            else (existing.supports_vision if existing is not None else False)
        )

        info = ProviderInfo(
            name=name,
            client_class=type(client),
            default_models=(
                [model.model_id for model in models]
                if models
                else (list(existing.default_models) if existing is not None else [])
            ),
            supports_streaming=supports_streaming,
            supports_tools=supports_tools,
            supports_vision=supports_vision,
            base_url=existing.base_url if existing is not None else None,
            docs_url=existing.docs_url if existing is not None else None,
            pricing_url=existing.pricing_url if existing is not None else None,
            description=existing.description if existing is not None else "",
        )
        super().register(name, info, allow_overwrite=True)
        self._provider_clients[name] = client
        if models:
            self._provider_models[name] = list(models)

    async def get_client(self, provider: str) -> LLMClientProtocol | None:
        """Get an initialized client for a provider."""
        return self._provider_clients.get(provider)

    def list_models(
        self, capabilities: set[ModelCapability] | None = None
    ) -> list[ModelInfo]:
        """List all models matching capabilities."""
        from quadkit.contracts.ai.providers import ModelInfo
        from quadkit.contracts.ai.types import ModelCapability

        models: list[ModelInfo] = []
        for provider_info in self.values():
            registered_models = self._provider_models.get(provider_info.name)
            if registered_models is not None:
                provider_models = registered_models
            else:
                provider_capabilities = {ModelCapability.CHAT}
                if provider_info.supports_streaming:
                    provider_capabilities.add(ModelCapability.STREAMING)
                if provider_info.supports_tools:
                    provider_capabilities.add(ModelCapability.FUNCTION_CALLING)
                if provider_info.supports_vision:
                    provider_capabilities.add(ModelCapability.VISION)
                provider_models = [
                    ModelInfo(
                        model_id=model_id,
                        provider=provider_info.name,
                        display_name=model_id,
                        capabilities=frozenset(provider_capabilities),
                        context_window=8192,
                        max_output_tokens=4096,
                        input_cost_per_million=0,
                        output_cost_per_million=0,
                    )
                    for model_id in provider_info.default_models
                ]

            for model in provider_models:
                if capabilities is not None and not capabilities.issubset(
                    model.capabilities
                ):
                    continue
                models.append(model)
        return models

    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get information about a specific model."""
        models = self.list_models()
        return next((m for m in models if m.model_id == model_id), None)
