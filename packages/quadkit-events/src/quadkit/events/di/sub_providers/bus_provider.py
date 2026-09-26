"""Sub-provider for CommandBusProtocol, QueryBusProtocol, EventBusProtocol creation (M-01)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts import HealthCheckResult, HealthStatus

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerRegistrarProtocol
    from quadkit.events.config import EventsConfig


class BusSubProvider:
    """Focused sub-provider: creates and owns the three message buses.

    Example::

        sub = BusSubProvider(config)
        await sub.setup()
        bus = sub.event_bus
    """

    def __init__(self, config: EventsConfig) -> None:
        self._config = config
        self._hooks: object | None = None
        self.command_bus: Any = None
        self.query_bus: Any = None
        self.event_bus: Any = None

    async def setup(self) -> None:
        """Instantiate all buses."""
        from quadkit.events.buses import CommandBusImpl, EventBusImpl, QueryBusImpl

        self.command_bus = CommandBusImpl(config=self._config.command_bus)
        self.query_bus = QueryBusImpl(config=self._config.query_bus)
        self.event_bus = EventBusImpl(config=self._config.event_bus, hooks=self._hooks)  # type: ignore[arg-type]

    async def boot(self) -> None:
        """Start buses that expose a start() method."""
        for bus in (self.command_bus, self.query_bus, self.event_bus):
            if bus and hasattr(bus, "start"):
                await bus.start()

    def set_tracer(self, tracer: object | None) -> None:
        """Wire tracer into the event bus if supported.

        Args:
            tracer: Tracer instance or None to clear.
        """
        if self.event_bus is not None and hasattr(self.event_bus, "set_tracer"):
            self.event_bus.set_tracer(tracer)

    def set_hook_registry(self, hooks: object | None) -> None:
        """Wire an optional hook registry into the event bus if supported."""
        self._hooks = hooks
        if self.event_bus is not None and hasattr(self.event_bus, "set_hook_registry"):
            self.event_bus.set_hook_registry(hooks)

    def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register buses into the DI container (both concrete and core types)."""
        from quadkit.contracts.events import (
            CommandBusProtocol as CoreCommandBus,
        )
        from quadkit.contracts.events import (
            EventBusProtocol as CoreEventBus,
        )
        from quadkit.contracts.events import (
            QueryBusProtocol as CoreQueryBus,
        )
        from quadkit.events.buses import CommandBusImpl, EventBusImpl, QueryBusImpl

        def _register_bus(
            concrete_cls: type[Any], core_cls: type[Any], instance: object | None
        ) -> None:
            if instance is None:
                return
            container.singleton(concrete_cls, instance)
            if container.has(core_cls):
                container.override(core_cls, instance)  # type: ignore[attr-defined]
            else:
                container.singleton(core_cls, instance)

        _register_bus(CommandBusImpl, CoreCommandBus, self.command_bus)
        _register_bus(QueryBusImpl, CoreQueryBus, self.query_bus)
        _register_bus(EventBusImpl, CoreEventBus, self.event_bus)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return health status for all buses."""
        details: dict[str, Any] = {}
        all_healthy = True
        for name, bus in [
            ("command_bus", self.command_bus),
            ("query_bus", self.query_bus),
            ("event_bus", self.event_bus),
        ]:
            if bus and hasattr(bus, "health_check"):
                try:
                    hc = await bus.health_check(timeout=timeout)
                    details[name] = hc.to_dict() if hasattr(hc, "to_dict") else hc
                    if hasattr(hc, "status") and hc.status != HealthStatus.HEALTHY:
                        all_healthy = False
                except Exception as exc:  # noqa: BLE001 — a component health-check failure degrades the aggregate, never raises
                    details[name] = {
                        "status": HealthStatus.UNHEALTHY,
                        "error": str(exc),
                    }
                    all_healthy = False
            elif bus:
                details[name] = {"status": HealthStatus.UNKNOWN}
        return HealthCheckResult(
            component="buses",
            status=HealthStatus.HEALTHY if all_healthy else HealthStatus.DEGRADED,
            details=details,
        )


__all__ = ["BusSubProvider"]
