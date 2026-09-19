"""Provider registry for storing and querying provider instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.di._graph import ProviderGraph
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.module.dynamic import DynamicModule
    from quadkit.di.module.graph import CompiledModuleGraph
    from quadkit.di.provider import Provider

logger = get_logger(__name__)


class ProviderRegistry:
    """Registry for provider instances.

    Stores providers by name, handles deduplication, and provides
    query methods. Does NOT manage lifecycle.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._providers: dict[str, Provider] = {}
        self._compiled_graph: CompiledModuleGraph | None = None
        self._graph = ProviderGraph(self._providers)

    @property
    def graph(self) -> ProviderGraph:
        """Return the dependency graph for this registry."""
        return self._graph

    def add(self, provider: Provider) -> None:
        """Add a provider to the registry.

        Recursively adds sub-providers for unified lifecycle management.
        Silently ignores exact-type duplicates; raises ValueError on name conflicts.

        Args:
            provider: Provider instance to register.

        Raises:
            ValueError: If a different provider with the same name is already registered.
        """
        if provider.name in self._providers:
            existing = self._providers[provider.name]
            if type(existing) is type(provider):
                logger.debug("orchestrator.add.duplicate_ignored", name=provider.name)
                return
            raise ValueError(
                f"Duplicate provider name: {provider.name!r}. "
                f"Existing: {type(existing).__name__}, "
                f"New: {type(provider).__name__}",
            )

        self._providers[provider.name] = provider

        # Recursively add sub-providers (if any)
        if hasattr(provider, "sub_providers"):
            for sub in provider.sub_providers:
                self.add(sub)

    def add_module(self, module_cls: type | DynamicModule) -> None:
        """Extract providers from a module and register them.

        Accepts both a ``@module``-decorated class and a
        :class:`~quadkit.di.module.dynamic.DynamicModule` instance.

        Args:
            module_cls: A ``@module``-decorated class or
                :class:`~quadkit.di.module.dynamic.DynamicModule`.

        Raises:
            ValueError: If ``module_cls`` is a class not decorated with
                ``@module``.
        """
        from quadkit.di.module.constants import MODULE_METADATA_ATTR
        from quadkit.di.module.dynamic import DynamicModule

        if isinstance(module_cls, DynamicModule):
            for p in module_cls.providers:
                self.add(p if not isinstance(p, type) else p())
        else:
            meta = getattr(module_cls, MODULE_METADATA_ATTR, None)
            if meta is None:
                raise ValueError(
                    f"{module_cls.__name__!r} is not a module — "
                    f"decorate it with @module first.",
                )
            for provider_cls in meta.providers:
                self.add(
                    provider_cls() if isinstance(provider_cls, type) else provider_cls
                )

    def get(self, name: str) -> Provider | None:
        """Return the provider with the given name, or None.

        Args:
            name: Provider name to look up.

        Returns:
            The provider instance or None if not found.
        """
        return self._providers.get(name)

    def all(self) -> list[Provider]:
        """Return all registered providers in insertion order.

        Returns:
            List of all provider instances.
        """
        return list(self._providers.values())

    def names(self) -> list[str]:
        """Return all registered provider names.

        Returns:
            List of provider name strings.
        """
        return list(self._providers.keys())


__all__ = ["ProviderRegistry"]
