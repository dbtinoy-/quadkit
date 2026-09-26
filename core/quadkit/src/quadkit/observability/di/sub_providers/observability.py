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
        """Register the no-op observability implementations.

        These bindings are fallbacks: they let application code compile and
        run without ``quadkit-monitor``, but they must never win over a real
        implementation. The container overwrites a token with the last
        registration, so registering unconditionally makes the winner depend
        on module composition order — and in nested module graphs this
        provider lands *after* ``MonitorProvider`` and suppresses the concrete
        collector. Guard each token, the same pattern the other fallback
        sites use (``quadkit-auth``, ``quadkit-cache``, ``the optional provider``),
        so whichever real implementation registered first survives.
        """
        collector = NoOpMetricsCollector()
        if not container.has(MetricsCollectorProtocol):
            container.singleton(MetricsCollectorProtocol, collector)
        if not container.has(MetricsRecorderProtocol):
            container.singleton(MetricsRecorderProtocol, collector)
        if not container.has(MetricsFactoryProtocol):
            container.singleton(MetricsFactoryProtocol, collector)

        if not container.has(TracerProtocol):
            container.singleton(TracerProtocol, NoOpTracer())

        registry = NoOpHealthCheckRegistry()
        if not container.has(HealthCheckRegistryProtocol):
            container.singleton(HealthCheckRegistryProtocol, registry)
        if not container.has(HealthCheckProtocol):
            container.singleton(HealthCheckProtocol, registry)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """No boot-time work is required."""

    async def shutdown(self) -> None:
        """No resources need teardown."""


__all__ = ["ObservabilityProvider"]
