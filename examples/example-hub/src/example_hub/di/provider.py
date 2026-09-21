"""Convention followed: **Provider pattern** — ``register()`` declares singletons, ``boot()`` resolves contracts, ``health_check()`` reports readiness.

DI wiring for the demo hub.

A Provider tells the DI container *what* exists and *how* to build it.
Two-phase lifecycle: ``register()`` binds, ``boot()`` initializes.

Simplest patterns for new users:

- ``container.singleton(Thing, instance=Thing())`` — already built, hand it over
- ``container.singleton(Thing, factory=lambda: ...)`` — build lazily on first resolve
- ``container.singleton(Thing, factory=self._build_thing)`` — async factory for complex wiring

Don't re-register framework keys (e.g. ``WebConfig``) — the
web module already owns them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from example_hub.controllers.api import HubApiController
from example_hub.fleet import Fleet
from example_hub.services.registry import ServiceRegistry
from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)

__all__ = ["HubProvider"]


class HubProvider(Provider):
    """Demo-specific DI registrations — your app replaces this.

    Provider lifecycle: register() → boot() → shutdown().
    register() binds services (no I/O); boot() initializes after freeze.
    """

    name = "example_hub"

    _fleet: Fleet | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind demo services — no I/O here.

        ``container.singleton(Thing, instance=Thing())`` for already-built objects.
        ``container.singleton(Thing, factory=async_fn)`` for services that need
        other services resolved first (async factories run during resolve).
        """
        # --- Registry: empty at boot, populated by Fleet ---
        # ServiceRegistry is a plain data structure that lists all demos
        # with their slugs, ports, and capabilities.  Fleet populates it
        # during mount_all().
        registry = ServiceRegistry()
        container.singleton(ServiceRegistry, instance=registry)

        # --- Fleet: built lazily via factory ---
        # Fleet depends on ServiceRegistry, so we use a lambda factory.
        # The factory closes over `registry` — no resolution needed here.
        container.singleton(Fleet, factory=lambda: Fleet(registry))

        # --- Controller: bound directly as instance ---
        # HubApiController is stateless at register time — Fleet is
        # injected during boot() via container.bind().
        container.singleton(HubApiController, HubApiController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve Fleet and rebind the controller — I/O is allowed here.

        boot() runs AFTER register() completes and the container is frozen.
        This is where you resolve services and do initialization work
        (seeding data, warming caches, connecting to external services).
        """
        # Resolve Fleet — this triggers the factory, which creates Fleet
        # with the empty ServiceRegistry.
        self._fleet = await container.resolve(Fleet)

        # Rebind the controller with Fleet attached.  Controllers are
        # normally constructed by the router from the container, but
        # HubApiController needs Fleet — so we construct it here and
        # rebind the container to use our instance.
        container.bind(HubApiController, HubApiController(fleet=self._fleet))
        logger.info("hub_fleet_resolved")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report fleet readiness (mounted vs failed children)."""
        fleet = self._fleet
        details = (
            {"mounted": len(fleet.mounted), "failures": len(fleet.failures)}
            if fleet is not None
            else {"mounted": 0, "failures": 0}
        )
        status = (
            HealthStatus.HEALTHY
            if fleet is not None and not fleet.failures
            else HealthStatus.DEGRADED
        )
        return HealthCheckResult(
            component=self.name,
            status=status,
            category=HealthCheckCategory.READINESS,
            details=details,
        )
