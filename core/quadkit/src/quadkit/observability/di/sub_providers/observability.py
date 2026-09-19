"""No-op observability provider registered by the Quadkit core framework."""

from __future__ import annotations

from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.core.health import HealthCheckProtocol
from quadkit.contracts.observability.metrics import (
    HealthCheckRegistryProtocol,
    MetricsCollectorProtocol,
    MetricsFactoryProtocol,
    MetricsRecorderProtocol,
)
from quadkit.contracts.observability.tracing import TracerProtocol
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.observability.core import (
    NoOpHealthCheckRegistry,
    NoOpMetricsCollector,
    NoOpTracer,
)


class ObservabilityProvider(Provider):
    """Provides no-op observability bindings for the core framework."""

    name = "observability"
    priority = ProviderPriority.INFRASTRUCTURE

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register the no-op observability implementations."""
        collector = NoOpMetricsCollector()
        container.singleton(MetricsCollectorProtocol, collector)
        container.singleton(MetricsRecorderProtocol, collector)
        container.singleton(MetricsFactoryProtocol, collector)

        tracer = NoOpTracer()
        container.singleton(TracerProtocol, tracer)

        registry = NoOpHealthCheckRegistry()
        container.singleton(HealthCheckRegistryProtocol, registry)
        container.singleton(HealthCheckProtocol, registry)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """No boot-time work is required."""

    async def shutdown(self) -> None:
        """No resources need teardown."""


__all__ = ["ObservabilityProvider"]
