"""EventsProvider implementation (M-01).

Thin orchestrator that coordinates Events sub-providers.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.core import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
    ProviderPriority,
)
from quadkit.di.provider import Provider
from quadkit.events.config import EventsConfig
from quadkit.events.di.sub_providers.bus_provider import BusSubProvider
from quadkit.events.di.sub_providers.handler_provider import HandlerSubProvider
from quadkit.events.di.sub_providers.manager_provider import ManagerSubProvider
from quadkit.events.di.sub_providers.store_provider import StoreSubProvider
from quadkit.events.types import EventStoreBackend
from quadkit.logging import get_logger


async def _resolve_optional_framework_service(
    container: Any, service_type: type
) -> Any:
    """Resolve an optional framework service without crossing module boundaries.

    Provider boot hooks run inside their owning module's visibility context.
    Cross-cutting services such as tracing and hooks are intentionally wired by
    the framework, so their optional lookup must use the internal visibility
    bypass. Small test doubles and older resolver implementations may not
    accept that keyword; those fall back to their optional resolver.
    """
    from inspect import Parameter, signature

    from quadkit.contracts.exceptions.container import UnresolvableDependencyError

    resolver = getattr(container, "resolve", None)
    if resolver is None:
        return await container.resolve_optional(service_type)

    try:
        parameters = signature(resolver).parameters.values()
        supports_bypass = any(
            parameter.name == "bypass_visibility"
            or parameter.kind is Parameter.VAR_KEYWORD
            for parameter in parameters
        )
    except (TypeError, ValueError):
        # Resolver proxies may not expose a useful signature; the canonical
        # container supports the keyword, so prefer the internal path.
        supports_bypass = True

    if not supports_bypass:
        # Compatibility with lightweight resolver doubles that predate the
        # internal bypass keyword.
        return await container.resolve_optional(service_type)

    try:
        return await resolver(service_type, bypass_visibility=True)
    except (LookupError, UnresolvableDependencyError):
        return None


if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


class EventsProvider(Provider):
    """Thin orchestrator that coordinates Events sub-providers (M-01).

    Delegates all setup, lifecycle, and container-registration work to:

    - :class:`StoreSubProvider`
    - :class:`BusSubProvider`
    - :class:`HandlerSubProvider`
    - :class:`ManagerSubProvider`

    Public API is unchanged from the monolithic version.
    """

    name = "events"
    priority = ProviderPriority.INFRASTRUCTURE
    config_key: str | None = "events"
    config_model: type | None = EventsConfig

    def __init__(
        self,
        config: EventsConfig | dict[str, Any] | None = None,
        handler_modules: list[str] | None = None,
    ) -> None:
        super().__init__()

        if isinstance(config, dict):
            config = EventsConfig(**config)

        # Explicit config composes eagerly; zero-config construction leaves
        # ``_config`` as None so the orchestrator can inject the yaml section
        # (via ``config_key``) after construction — sub-providers are then
        # composed in ``_ensure_composed()`` during ``register()``.
        self._config: EventsConfig | None = config
        self._handler_modules = handler_modules or []

        self._stores: StoreSubProvider | None = None
        self._buses: BusSubProvider | None = None
        self._managers: ManagerSubProvider | None = None
        if config is not None:
            self._compose_sub_providers()

    def _compose_sub_providers(self) -> None:
        """(Re)build store and bus sub-providers from ``self._config``.

        Called eagerly from ``__init__`` when explicit config was supplied and
        again from ``_ensure_composed()`` when injection arrived late (i.e.
        ``configure()`` ran with no explicit config).
        """
        cfg = self._config
        if cfg is None:
            cfg = EventsConfig(
                event_store_backend=EventStoreBackend.MEMORY,
                debug=False,
            )
            self._config = cfg
        self._stores = StoreSubProvider(cfg)
        self._buses = BusSubProvider(cfg)

    def _ensure_composed(self) -> tuple[StoreSubProvider, BusSubProvider, EventsConfig]:
        """Return the composed sub-providers, building them on first need.

        Returns:
            The ``(stores, buses, config)`` triple, composed from the current
            ``self._config`` (yaml-injected or framework defaults).
        """
        if self._stores is None or self._buses is None:
            self._compose_sub_providers()
        stores = cast("StoreSubProvider", self._stores)
        buses = cast("BusSubProvider", self._buses)
        cfg = cast("EventsConfig", self._config)
        return stores, buses, cfg

    @classmethod
    def from_config(cls, config: EventsConfig, **context: Any) -> EventsProvider:
        """Create EventsProvider from config."""
        return cls(config=config, handler_modules=context.get("handler_modules"))

    @property
    def config(self) -> EventsConfig | None:
        return self._config

    @config.setter
    def config(self, value: EventsConfig) -> None:
        """Allow orchestrator to auto-inject config from QuadkitConfig."""
        if isinstance(value, dict):
            value = EventsConfig(**value)
        self._config = value
        self._compose_sub_providers()

    @property
    def event_store(self) -> Any:
        stores, _, _ = self._ensure_composed()
        return stores.event_store

    @property
    def snapshot_manager(self) -> Any:
        stores, _, _ = self._ensure_composed()
        return stores.snapshot_manager

    @property
    def command_bus(self) -> Any:
        _, buses, _ = self._ensure_composed()
        return buses.command_bus

    @property
    def query_bus(self) -> Any:
        _, buses, _ = self._ensure_composed()
        return buses.query_bus

    @property
    def event_bus(self) -> Any:
        _, buses, _ = self._ensure_composed()
        return buses.event_bus

    @property
    def projection_manager(self) -> Any:
        return self._managers.projection_manager if self._managers else None

    @property
    def saga_manager(self) -> Any:
        return self._managers.saga_manager if self._managers else None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register all events components with the DI container."""
        stores, buses, cfg = self._ensure_composed()

        await stores.setup(container)
        stores.register(container)

        await buses.setup()
        buses.register(container)

        handlers = HandlerSubProvider(
            config=cfg,
            handler_modules=self._handler_modules,
            command_bus=buses.command_bus,
            query_bus=buses.query_bus,
            event_bus=buses.event_bus,
        )
        await handlers.setup(container)  # type: ignore[arg-type]

        self._managers = ManagerSubProvider(
            config=cfg,
            event_store=stores.event_store,
        )
        await self._managers.setup(container)
        self._managers.register(container)

        self._register_admin(cast("BootContainerProtocol", container))

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Start buses, managers, and wire optional tracer."""
        from quadkit.contracts.core import HookRegistryProtocol
        from quadkit.contracts.observability.tracing import TracerProtocol

        _, buses, _ = self._ensure_composed()

        tracer = await _resolve_optional_framework_service(container, TracerProtocol)
        hooks = await _resolve_optional_framework_service(
            container, HookRegistryProtocol
        )
        buses.set_tracer(tracer)
        buses.set_hook_registry(hooks)

        await buses.boot()
        if self._managers:
            await self._managers.boot()
        stores, _, _ = self._ensure_composed()
        if stores.snapshot_manager and hasattr(stores.snapshot_manager, "start"):
            await stores.snapshot_manager.start()

        await self._wire_adapters(container)

        from quadkit.events.admin.contributor import EventsAdminContributor

        try:
            contributor = await container.resolve(EventsAdminContributor)
            if hasattr(contributor, "on_admin_boot"):
                await contributor.on_admin_boot(container)
        except Exception as exc:  # noqa: BLE001
            logger.warning("events_admin_contributor_boot_failed", error=str(exc))

    async def _wire_adapters(self, container: ContainerResolverProtocol) -> None:
        """Connect registered adapters to the EventBusProtocol when configured."""
        from quadkit.contracts.events import EventBusProtocol
        from quadkit.events.adapters.registry import AdapterRegistry

        _, _, cfg = self._ensure_composed()

        event_bus = await container.resolve(EventBusProtocol)
        if event_bus is None:
            return

        # Wirers register connected adapters as singletons, so they need the
        # full boot container (the runtime object always provides it).
        registry = AdapterRegistry.with_defaults()
        await registry.wire_all(
            cfg, event_bus, cast("BootContainerProtocol", container)
        )

    async def shutdown(self) -> None:
        """Shutdown all components."""
        stores, _, _ = self._ensure_composed()
        await stores.teardown()
        if self._managers:
            await self._managers.teardown()

    def _register_admin(self, container: BootContainerProtocol) -> None:
        """Register admin widget handlers."""
        from quadkit.contracts.admin.protocols import AdminContributorProtocol
        from quadkit.contracts.events import EventBusProtocol, EventStoreProtocol
        from quadkit.events.admin.contributor import EventsAdminContributor
        from quadkit.events.admin.handlers.dead_letter_count import (
            DeadLetterCountWidgetHandler,
        )
        from quadkit.events.admin.handlers.events_throughput import (
            EventsThroughputWidgetHandler,
        )
        from quadkit.events.admin.handlers.live_events import (
            LiveEventsWidgetHandler,
        )

        async def _create_events_throughput_handler() -> EventsThroughputWidgetHandler:
            event_bus = await container.resolve(EventBusProtocol)
            return EventsThroughputWidgetHandler(event_bus=event_bus)

        async def _create_dead_letter_handler() -> DeadLetterCountWidgetHandler:
            event_bus = await container.resolve(EventBusProtocol)
            return DeadLetterCountWidgetHandler(event_bus=event_bus)

        async def _create_live_events_handler() -> LiveEventsWidgetHandler:
            event_store = await container.resolve(EventStoreProtocol)
            return LiveEventsWidgetHandler(event_store=event_store)

        container.transient(
            EventsThroughputWidgetHandler,
            _create_events_throughput_handler,
        )
        container.transient(
            DeadLetterCountWidgetHandler,
            _create_dead_letter_handler,
        )
        container.transient(
            LiveEventsWidgetHandler,
            _create_live_events_handler,
        )
        container.singleton(EventsAdminContributor, EventsAdminContributor)
        container.singleton(
            AdminContributorProtocol,
            EventsAdminContributor,
        )

    async def _create_stores(
        self, container: ContainerRegistrarProtocol | None = None
    ) -> None:
        """Compat: delegates to StoreSubProvider.setup()."""
        stores, _, _ = self._ensure_composed()
        await stores.setup(container)

    @staticmethod
    def _health_payload(result: Any) -> dict[str, Any]:
        """Normalize health result implementations to JSON-safe dictionaries."""
        if isinstance(result, dict):
            return result

        for method_name in ("to_dict", "model_dump"):
            serializer = getattr(result, method_name, None)
            if callable(serializer):
                payload = serializer()
                if isinstance(payload, dict):
                    return payload

        status = getattr(result, "status", HealthStatus.UNKNOWN)
        return {"status": getattr(status, "value", str(status))}

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Aggregate health across stores and buses."""
        start = time.time()
        overall = HealthStatus.HEALTHY
        details: dict[str, Any] = {"components": {}}
        errors: list[str] = []

        stores, buses, _ = self._ensure_composed()

        bus_health = await buses.health_check(timeout=timeout)
        details["components"]["buses"] = self._health_payload(bus_health)
        if bus_health.status != HealthStatus.HEALTHY:
            overall = HealthStatus.DEGRADED

        if stores.event_store and hasattr(stores.event_store, "health_check"):
            try:
                sh = await stores.event_store.health_check(timeout=timeout)
                details["components"]["event_store"] = self._health_payload(sh)
                if hasattr(sh, "status") and sh.status != HealthStatus.HEALTHY:
                    overall = HealthStatus.DEGRADED
            except Exception as exc:  # noqa: BLE001 — a component health-check failure degrades the aggregate, never raises
                details["components"]["event_store"] = {
                    "status": "unhealthy",
                    "error": str(exc),
                }
                overall = HealthStatus.DEGRADED
                errors.append(f"EventStoreProtocol: {exc}")
        elif stores.event_store:
            details["components"]["event_store"] = {"status": "unknown"}
            overall = HealthStatus.DEGRADED

        return HealthCheckResult(
            component="events",
            status=overall,
            details=details,
            error=" | ".join(errors) if errors else None,
            duration_ms=(time.time() - start) * 1000,
            category=HealthCheckCategory.READINESS,
        )


__all__ = ["EventsProvider"]
