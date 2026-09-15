"""DI Provider for the di subsystem.

The ONLY file that registers di infrastructure into
the Quadkit DI container.
"""

from __future__ import annotations

from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider, ProviderPriority


class DiProvider(Provider):
    """Dependency injection container, providers, and resolution engine DI provider."""

    name = "di"
    priority = ProviderPriority.INFRASTRUCTURE

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register di services into *container*.

        Binding ``ContainerResolverProtocol`` to the container instance itself allows
        other providers and modules to declare it as a constructor dependency
        and have it auto-injected — the canonical DI alternative to the
        Service Locator anti-pattern.
        """
        from quadkit.di.container import Container

        # The container IS the ContainerResolverProtocol — register it so that
        # CoreModule's declared export is satisfied.
        if isinstance(container, Container):
            container.singleton(ContainerResolverProtocol, container, validate=False)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Apply DiConfig settings at boot.

        Wires: ``type_hint_cache_size`` (type-hint LRU), ``max_resolution_depth``
        and ``debug_resolution`` (resolver), ``strict_mode`` and
        ``validate_on_register`` (container).
        """
        from quadkit.di.config.models import DiConfig
        from quadkit.di.container import Container
        from quadkit.di.resolution.resolver import ServiceResolver
        from quadkit.di.resolution.type_hints import TypeHintResolverImpl

        config: DiConfig = (
            await container.resolve_optional(DiConfig)
            if container.has(DiConfig)
            else None
        ) or DiConfig()
        TypeHintResolverImpl.configure(config.type_hint_cache_size)
        ServiceResolver.configure(
            max_resolution_depth=config.max_resolution_depth,
            debug_resolution=config.debug_resolution,
        )
        if isinstance(container, Container):
            container.strict_mode = config.strict_mode
            container.validate_on_register = config.validate_on_register

    async def shutdown(self) -> None:
        """Shut down di services gracefully."""


__all__ = [
    "DiProvider",
]
