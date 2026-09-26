"""Convention followed: **Provider pattern** — ``register()`` declares singletons, ``boot()`` resolves contracts, ``health_check()`` reports readiness.

DI wiring for the event-driven orders demo — Provider lifecycle pattern.

A Provider tells the DI container *what* exists and *how* to build it.
Two-phase lifecycle: ``register()`` binds, ``boot()`` initializes.

Simplest patterns for new users:

- ``container.singleton(Thing, instance=Thing())`` — already built, hand it over
- ``container.singleton(Thing, factory=lambda: ...)`` — build lazily on first resolve
- ``container.singleton(Thing, factory=self._build_thing)`` — async factory for complex wiring

This demo wires the **CQRS write side** (repository, command handlers, outbox)
and the **read side** (projection, notifications) onto the framework's
in-memory command and event buses.  All handlers are constructor-injected
services — no service locator.

Convention: one Provider per bounded context; ``register()`` does binding
(no I/O), ``boot()`` does initialization (I/O allowed).
"""

from __future__ import annotations

from orders.commands import PayOrder, PlaceOrder, ShipOrder
from orders.config import OrdersConfig
from orders.domain import OrderPaid, OrderPlaced, OrderShipped
from orders.events import NotificationHandler, OrdersView
from orders.handlers import PayOrderHandler, PlaceOrderHandler, ShipOrderHandler
from orders.repository.order_repository import OrderRepository
from orders.repository.outbox import Outbox
from orders.services.orders_api import OrdersApi
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.core.health import (
    HealthCheckResult,
)
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.contracts.events import CommandBusProtocol, EventBusProtocol
from quadkit.di.provider import Provider


class OrdersProvider(Provider):
    """Demo-specific DI registrations — your app replaces this.

    Provider lifecycle: register() -> boot() -> shutdown().
    register() binds services (no I/O); boot() initializes after freeze.
    """

    name = "orders"
    config_key: str | None = "orders"
    config_model: type | None = OrdersConfig
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind demo services — no I/O here.

        ``container.singleton(Thing, instance=Thing())`` for already-built objects.
        ``container.singleton(Thing, factory=async_fn)`` for services that need
        other services resolved first (async factories run during resolve).
        """
        cfg = self.config or OrdersConfig()
        container.singleton(OrdersConfig, instance=cfg)

        # --- Write side: repository + outbox, bind as instances ---
        # In-memory stores with no framework dependencies — register as
        # instances for simplicity.  In production, swap for database-backed
        # implementations.
        container.singleton(OrderRepository, OrderRepository)

        # --- Read side: projection + notification handler ---
        # OrdersView is the query-side projection fed exclusively by events.
        # NotificationHandler is a side-effect handler (emails, webhooks).
        container.singleton(OrdersView, OrdersView)
        container.singleton(NotificationHandler, NotificationHandler)

        # --- Outbox: transactional outbox pattern ---
        # Command handlers stage events here; the outbox relay delivers them
        # through the event bus.  In production, outbox rows live in the same
        # DB transaction as the write-side state.
        container.singleton(Outbox, Outbox)

        # --- Facade: async factory for complex wiring ---
        # The facade needs buses resolved from the container (which aren't
        # available during register()).  Use a factory so the bus wiring
        # happens lazily on first resolve.
        container.singleton(OrdersApi, factory=self._build_api)

    async def _build_api(self, resolver: ContainerResolverProtocol) -> OrdersApi:
        """Register handlers/subscriptions, then assemble the facade.

        This async factory runs during resolve (after register() completes
        and the container is frozen).  It wires command handlers onto the
        command bus and event subscriptions onto the event bus, then builds
        the facade that ties everything together.
        """
        # --- Write side: register command handlers on the command bus ---
        # Each handler receives the repository and outbox via constructor
        # injection.  The command bus dispatches commands to handlers by type.
        repository = await resolver.resolve(OrderRepository)
        outbox = await resolver.resolve(Outbox)
        command_bus = await resolver.resolve(CommandBusProtocol)
        command_bus.register(
            PlaceOrder,
            PlaceOrderHandler(repository=repository, outbox=outbox),
        )
        command_bus.register(
            PayOrder,
            PayOrderHandler(repository=repository, outbox=outbox),
        )
        command_bus.register(
            ShipOrder,
            ShipOrderHandler(repository=repository, outbox=outbox),
        )

        # --- Read side: subscribe event handlers on the event bus ---
        # The projection (OrdersView) and notification handler react to
        # published domain events.  The event bus dispatches events to
        # all subscribers by event type.
        event_bus = await resolver.resolve(EventBusProtocol)
        view = await resolver.resolve(OrdersView)
        notifier = await resolver.resolve(NotificationHandler)
        event_bus.subscribe(OrderPlaced, view.on_order_placed)
        event_bus.subscribe(OrderPaid, view.on_order_paid)
        event_bus.subscribe(OrderShipped, view.on_order_shipped)
        event_bus.subscribe(OrderPlaced, notifier.on_order_placed)
        event_bus.subscribe(OrderShipped, notifier.on_order_shipped)

        # --- Assemble the facade ---
        # OrdersApi is the single entry point for REST controllers.
        # It dispatches commands and queries through the wired buses.
        return OrdersApi(
            command_bus=command_bus,
            event_bus=event_bus,
            repository=repository,
            view=view,
            outbox=outbox,
        )

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Wire handlers/subscriptions eagerly, before the app serves.

        boot() runs AFTER register() completes and the container is frozen.
        This is where you resolve services and do initialization work
        (seeding data, warming caches, connecting to external services).

        Resolving ``OrdersApi`` triggers ``_build_api`` exactly once
        (singleton), reproducing the original boot-time wiring contract:
        any consumer may dispatch or publish straight after start().
        """
        self._api = await container.resolve(OrdersApi)

    async def shutdown(self) -> None:
        """Nothing to tear down; the demo is fully in-memory."""

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report write/read-side readiness with outbox depth."""
        return HealthCheckResult(
            component=self.name,
            message=f"{cfg.service_name} provider ready",
            details={
                "wired": getattr(self, "_api", None) is not None,
                "outbox_depth": (
                    len(self._api.list_outbox()) if getattr(self, "_api", None) else 0
                ),
            },
        )


__all__ = ["OrdersProvider"]
