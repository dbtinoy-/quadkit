"""ProviderOrchestrator — facade coordinating the DI provider lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.health import AggregateHealthResult, HealthCheckCategory
from quadkit.di.orchestrator.events import LifecycleEventEmitter
from quadkit.di.orchestrator.health import HealthCoordinator
from quadkit.di.orchestrator.lifecycle import LifecycleManager
from quadkit.di.orchestrator.registry import ProviderRegistry
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )
    from quadkit.di.container import Container
    from quadkit.di.module.dynamic import DynamicModule
    from quadkit.di.module.graph import CompiledModuleGraph
    from quadkit.di.provider import Provider

logger = get_logger(__name__)


class ProviderOrchestrator:
    """Facade orchestrating the DI provider lifecycle.

    Composes ProviderRegistry, LifecycleManager, HealthCoordinator,
    and LifecycleEventEmitter into a single cohesive interface.

    Guarantees three-phase lifecycle:
        Phase 1: register() — ALL providers bind into the container.
        Phase 2: boot()     — ALL providers initialize (safe to resolve).
        Phase 3: shutdown() — ALL providers tear down (reverse boot order).

    Lifecycle hooks:
        - OnModuleInitProtocol: Called after each provider boots.
        - OnApplicationBootstrapProtocol: Called after ALL providers boot.
        - OnBeforeShutdownProtocol: Called before shutdown begins.
        - OnApplicationShutdownProtocol: Called after ALL providers shut down.
    """

    def __init__(self, container: Container) -> None:
        """Initialize the orchestrator with a DI container.

        Args:
            container: The DI container to register and resolve services from.
        """
        self._container = container
        self._registry = ProviderRegistry()
        self._events = LifecycleEventEmitter(self._registry)
        self._lifecycle = LifecycleManager(self._registry, self._events)
        self._health = HealthCoordinator(self._registry)

    # -- Internal access for Application base class (package-private) ------

    @property
    def _providers(self) -> dict[str, Any]:
        """Internal: Direct access to provider dict for Application base class.

        Returns the underlying dict so mutations (clear, update) are reflected
        in the registry without additional API surface.
        """
        return self._registry._providers

    @property
    def _compiled_graph(self) -> CompiledModuleGraph | None:
        """Internal: Get compiled module graph."""
        return self._registry._compiled_graph

    @_compiled_graph.setter
    def _compiled_graph(self, value: CompiledModuleGraph | None) -> None:
        """Internal: Set compiled module graph (used by Application boot)."""
        self._registry._compiled_graph = value

    @property
    def _graph(self) -> Any:
        """Internal: Expose registry graph for tests and boot_levels access."""
        return self._registry.graph

    # -- Provider registration ---------------------------------------------

    def clear_providers(self) -> None:
        """Remove all registered providers from the orchestrator.

        Used by the Application boot sequence when module compilation
        re-orders providers; call this before re-populating via :meth:`add`.

        Example::

            orchestrator.clear_providers()
            for entry in graph.provider_order:
                orchestrator.add(entry.provider)
        """
        self._registry._providers.clear()

    def set_compiled_graph(self, graph: CompiledModuleGraph | None) -> None:
        """Store the compiled module dependency graph.

        Called by the Application boot sequence after :class:`ModuleCompiler`
        has produced a resolved, ordered :class:`CompiledModuleGraph`.  The
        graph is forwarded to the underlying :class:`ProviderRegistry` so that
        health-check and visibility logic can query module relationships.

        Args:
            graph: The compiled graph produced by ``ModuleCompiler.compile()``,
                or ``None`` to clear any previously stored graph.
        """
        self._registry._compiled_graph = graph

    @property
    def compiled_graph(self) -> CompiledModuleGraph | None:
        """The compiled module graph, or ``None`` before compilation.

        The public companion to :meth:`set_compiled_graph`. The graph is what
        knows which module declares which export, and the code that needs to
        answer that question lives outside this class: health probes, boot-time
        assertions, and test guards. Without a reader the only way to ask was
        the private ``_compiled_graph``, so every such caller reached into the
        orchestrator's internals — and a rename would have broken them without
        a test to notice.

        Returns:
            The graph produced by :class:`ModuleCompiler`, or ``None`` when the
            application has not been compiled yet.
        """
        return self._registry._compiled_graph

    def add(self, provider: Provider) -> None:
        """Add a provider to be orchestrated.

        Recursively adds sub-providers for unified lifecycle management.

        Args:
            provider: Provider instance to register.
        """
        self._registry.add(provider)

    def add_module(self, module_cls: type | DynamicModule) -> None:
        """Extract providers from a module and register them.

        Args:
            module_cls: A ``@module``-decorated class or DynamicModule.
        """
        self._registry.add_module(module_cls)

    # -- Lifecycle phases --------------------------------------------------

    async def register_all(
        self, container: ContainerRegistrarProtocol | None = None
    ) -> None:
        """Phase 1: Register all providers with the container.

        Args:
            container: Override registrar. Defaults to the container passed at init.
        """
        await self._lifecycle.register_all(container or self._container)

    async def boot_all(self, container: Container | None = None) -> None:
        """Execute full startup: register, validate, then boot.

        Args:
            container: Override container. Defaults to the container passed at init.
        """
        await self._lifecycle.boot_all(container or self._container)

    async def boot_only(self, resolver: BootContainerProtocol | None = None) -> None:
        """Phase 2: Boot all registered providers.

        Args:
            resolver: Override container for boot. Defaults to the container passed at init.
        """
        await self._lifecycle.boot_only(resolver or self._container)

    async def shutdown(self, signal: str | None = None) -> None:
        """Phase 3: Shutdown all providers in reverse boot order.

        Args:
            signal: Optional signal name that triggered the shutdown.
        """
        await self._lifecycle.shutdown(signal)

    # -- Health check ------------------------------------------------------

    async def health_check(self, timeout: float = 5.0) -> dict[str, Any]:
        """Run health checks across all providers concurrently.

        Args:
            timeout: Maximum seconds to wait per provider health check.

        Returns:
            Mapping of provider name to HealthCheckResult.
        """
        return await self._health.check_all(timeout)

    async def run_all(
        self,
        timeout: float = 5.0,
        *,
        category: HealthCheckCategory | str | None = None,
    ) -> AggregateHealthResult:
        """Run all health checks and return the aggregated result."""
        return await self._health.run_all(timeout, category=category)

    async def run_liveness(self, timeout: float = 5.0) -> AggregateHealthResult:
        """Run liveness checks and return the aggregated result."""
        return await self._health.run_liveness(timeout)

    async def run_readiness(self, timeout: float = 5.0) -> AggregateHealthResult:
        """Run readiness checks and return the aggregated result."""
        return await self._health.run_readiness(timeout)

    async def run_startup(self, timeout: float = 5.0) -> AggregateHealthResult:
        """Run startup checks and return the aggregated result."""
        return await self._health.run_startup(timeout)

    def get_module_health_providers(self, module_cls: type) -> list[Provider]:
        """Return providers contributing to the given module's health check.

        Args:
            module_cls: The module class to get health providers for.

        Returns:
            List of Provider instances for this module's health check.
        """
        return self._health.get_module_health_providers(module_cls)

    # -- Query -------------------------------------------------------------

    @property
    def providers(self) -> list[Provider]:
        """Return all registered providers.

        Returns:
            List of all registered Provider instances.
        """
        return self._registry.all()

    @property
    def boot_order(self) -> list[str]:
        """Return provider names in the order they were booted.

        Returns:
            List of provider names in boot order.
        """
        return self._lifecycle.boot_order


__all__ = ["ProviderOrchestrator"]
