"""Convention followed: **Provider pattern** — ``register()`` declares singletons, ``boot()`` resolves contracts, ``health_check()`` reports readiness.

Lifecycle wiring for the focused Events Timeline Lab."""

from __future__ import annotations

from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.events import EventBusProtocol, EventStoreProtocol
from quadkit.di.provider import Provider
from timeline_lab.config import TimelineLabConfig
from timeline_lab.controllers.api import TimelineApiController
from timeline_lab.events import TimelineEvent
from timeline_lab.services.timeline import TimelineService


class TimelineLabProvider(Provider):
    """Wire public Events contracts to the browser-facing scenario."""

    name = "timeline_lab"
    config_key: str | None = "timeline_lab"
    config_model: type | None = TimelineLabConfig

    def __init__(self) -> None:
        super().__init__()
        self._service: TimelineService | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register controller type; resolving Events services waits for boot."""
        config = self.config or TimelineLabConfig()
        container.singleton(TimelineLabConfig, instance=config)
        container.singleton(TimelineApiController, TimelineApiController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve the package-owned bus and store, then subscribe handlers."""
        config = await container.resolve(TimelineLabConfig)
        event_bus = await container.resolve(EventBusProtocol)
        event_store = await container.resolve(EventStoreProtocol)
        self._service = TimelineService(event_bus, event_store, config)

        # These are application callbacks, but routing, retry, queueing, and
        # dispatch lifecycle are all provided by quadkit-events.
        event_bus.subscribe(TimelineEvent, self._service.record_delivery)
        event_bus.subscribe(TimelineEvent, self._service.failure_probe)
        container.bind(
            TimelineApiController,
            TimelineApiController(service=self._service),
        )

    async def shutdown(self) -> None:
        """EventsModule owns teardown of its bus and event store."""

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY if self._service else HealthStatus.UNHEALTHY,
            details={"wired": self._service is not None, "offline": True},
        )


__all__ = ["TimelineLabProvider"]
