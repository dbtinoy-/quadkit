"""DI Provider for the serialization subsystem.

Registers JSON serializers and the serializer registry as container singletons.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.di.provider import Provider, ProviderPriority

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )
    from quadkit.serialization.config import SerializationConfig


class SerializationProvider(Provider):
    """Serialization components DI provider."""

    name = "serialization"
    priority = ProviderPriority.INFRASTRUCTURE

    def __init__(self, config: SerializationConfig | None = None) -> None:
        """Initialise the provider with an optional pre-built config.

        Args:
            config: :class:`~quadkit.serialization.config.SerializationConfig`
                to use instead of the framework default.  When ``None`` the
                provider constructs a default ``SerializationConfig()`` at
                registration time.
        """
        super().__init__()
        self._config = config

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register serialization components."""
        from quadkit.contracts.core.serialization import JsonSerializerProtocol
        from quadkit.serialization.backends.json import (
            OrjsonSerializer,
            StdlibSerializer,
        )
        from quadkit.serialization.config import SerializationConfig
        from quadkit.serialization.registry import SerializerRegistry

        # Use caller-supplied config or fall back to defaults.
        config: SerializationConfig = (
            self._config if self._config is not None else SerializationConfig()
        )
        container.singleton(SerializationConfig, config)

        # Decide which JSON serializer to use as the primary implementation
        # of JsonSerializerProtocol
        primary_serializer: JsonSerializerProtocol
        try:
            import orjson  # noqa: F401, TID251

            primary_serializer = OrjsonSerializer(config)
        except ImportError:
            primary_serializer = StdlibSerializer(config)

        container.singleton(JsonSerializerProtocol, primary_serializer)

        # Register registry and add JSON to it
        registry = SerializerRegistry()
        registry.register("application/json", primary_serializer)
        container.singleton(SerializerRegistry, registry)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """No boot-time work required."""

    async def shutdown(self) -> None:
        """No resources to release."""

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Health check — always healthy (in-process only, no external backend).

        Args:
            timeout: Ignored for in-process providers.

        Returns:
            Always HEALTHY — no external backend to check.
        """
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"status": "operational"},
        )


__all__ = ["SerializationProvider"]
