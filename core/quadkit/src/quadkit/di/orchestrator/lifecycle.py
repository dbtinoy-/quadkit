"""Lifecycle manager for provider boot and shutdown phases."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from quadkit.contracts.exceptions.config import ConfigurationError
from quadkit.di.context import clear_module_context, set_module_context
from quadkit.di.provider import ProviderState
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )
    from quadkit.di.container import Container
    from quadkit.di.orchestrator.events import LifecycleEventEmitter
    from quadkit.di.orchestrator.registry import ProviderRegistry
    from quadkit.di.provider import Provider

logger = get_logger(__name__)


class LifecycleManager:
    """Manages provider boot and shutdown lifecycle.

    Orchestrates the three-phase lifecycle:
    Phase 1: register_all — all providers bind into the container.
    Phase 2: boot_only — all providers initialize in dependency order.
    Phase 3: shutdown — all providers tear down in reverse boot order.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        event_emitter: LifecycleEventEmitter,
    ) -> None:
        """Initialize with registry and event emitter.

        Args:
            registry: Provider registry containing all registered providers.
            event_emitter: Event emitter for lifecycle hook dispatch.
        """
        self._registry = registry
        self._events = event_emitter
        self._boot_order: list[str] = []
        self._lock = asyncio.Lock()

    @property
    def boot_order(self) -> list[str]:
        """Return the list of provider names in the order they were booted."""
        return list(self._boot_order)

    async def register_all(self, registrar: ContainerRegistrarProtocol) -> None:
        """Phase 1: Register all providers with the container.

        Validates provider dependencies, computes boot levels, and calls
        register() on each provider in parallel within each level.

        Args:
            registrar: Container registrar to bind services into.
        """
        if not self._registry._providers:
            return

        if all(
            p.state != ProviderState.CREATED for p in self._registry._providers.values()
        ):
            logger.debug("orchestrator.register.skip", reason="all_registered")
            return

        ordered = self._registry.graph.topological_sort()

        available = {p.name for p in ordered}
        for provider in ordered:
            for dep in getattr(provider, "dependencies", ()):
                if dep not in available:
                    from quadkit.contracts.exceptions.provider import ProviderError

                    raise ProviderError(
                        f"Provider '{provider.name}' depends on '{dep}' which is not registered. "
                        f"Available: {sorted(available)}",
                    )

        logger.info(
            "provider.register.start",
            count=len(ordered),
            order=[p.name for p in ordered],
        )

        levels = self._registry.graph.compute_boot_levels(ordered)

        logger.info(
            "provider.register.start",
            count=len(ordered),
            levels=[[p.name for p in level] for level in levels],
        )

        for level in levels:
            to_register = [p for p in level if p.state == ProviderState.CREATED]
            if not to_register:
                continue

            async def _register_one(p: Provider) -> None:
                t0 = time.perf_counter()
                tokens = set_module_context(
                    self._find_module_class(p), self._registry._compiled_graph
                )
                try:
                    await self._inject_provider_config(p, registrar)
                    await p.register(registrar)
                finally:
                    clear_module_context(tokens)
                p._state = ProviderState.REGISTERED
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                logger.debug(
                    "provider.registered",
                    provider=p.name,
                    elapsed_ms=elapsed_ms,
                )

            if len(to_register) == 1:
                await _register_one(to_register[0])
            else:
                await asyncio.gather(*[_register_one(p) for p in to_register])

    async def boot_all(self, container: Container) -> None:
        """Execute full startup: register, validate, then boot.

        Phases:
            1. register_all — all providers bind into the container.
            2. container.freeze() — registration closes to user code.
            3. container.validate() — dependency graph checked for issues.
            4. _validate_modules() — checks module export matching.
            5. boot_only — providers initialize in dependency order, inside
               a framework-managed registration window so boot-time
               materializers (``@provide`` factories) can bind their
               products. The window re-freezes on exit.

        Args:
            container: The DI container (implements both registrar and resolver).
        """
        from quadkit.contracts.exceptions.container import ContainerValidationError

        await self.register_all(container)
        if hasattr(container, "freeze"):
            container.freeze()

        issues = container.validate()
        module_issues = self._validate_modules()
        all_issues = issues + module_issues

        if all_issues:
            raise ContainerValidationError(all_issues)

        registrar = getattr(container, "registrar", container)
        registration_window = getattr(registrar, "_registration_window", None)
        if registration_window is None:
            await self.boot_only(container)
        else:
            with registration_window():
                await self.boot_only(container)

    async def boot_only(self, resolver: BootContainerProtocol) -> None:
        """Phase 2: Boot all registered providers.

        Boots providers in topologically sorted, parallel-level order.
        If any provider fails to boot, already-booted providers are
        shut down in reverse order as a rollback.

        Args:
            resolver: Container for boot phase (supports both resolve and register).
        """
        if not self._registry._providers:
            return

        if all(p.is_booted for p in self._registry._providers.values()):
            logger.debug("orchestrator.boot.skip", reason="all_booted")
            return

        ordered = self._registry.graph.topological_sort()
        levels = self._registry.graph.compute_boot_levels(ordered)

        logger.info(
            "provider.boot.start",
            levels=[[p.name for p in level] for level in levels],
        )

        async with self._lock:
            try:
                for level in levels:
                    to_boot = [p for p in level if not p.is_booted]
                    if not to_boot:
                        continue

                    if len(to_boot) == 1:
                        await self._boot_one(to_boot[0], resolver)
                    else:
                        await asyncio.gather(
                            *[self._boot_one(p, resolver) for p in to_boot],
                        )
            except Exception as e:  # noqa: BLE001 — rollback must run for any boot failure type
                logger.exception(
                    "provider.boot.failed",
                    error_type=type(e).__name__,
                    error=str(e),
                    boot_order=self._boot_order,
                )
                for name in reversed(self._boot_order):
                    provider = self._registry._providers.get(name)
                    if not provider:
                        continue
                    try:
                        await provider.shutdown()
                        provider._state = ProviderState.REGISTERED
                    except Exception as shutdown_error:  # noqa: BLE001 — every booted provider must attempt rollback
                        await provider.on_error(shutdown_error, "shutdown")
                        logger.warning(
                            "provider.rollback.failed",
                            provider=name,
                            error=str(shutdown_error),
                        )
                self._boot_order.clear()
                raise

        await self._events.emit_module_booted()
        await self._events.emit_application_bootstrap()

        logger.info("provider.boot.complete", count=len(self._boot_order))

    async def shutdown(self, signal: str | None = None) -> None:
        """Phase 3: Shutdown all providers in reverse boot order.

        All providers are shut down even if some fail. Errors are
        logged and the first error is re-raised after all shutdowns complete.

        Args:
            signal: Optional signal name that triggered the shutdown.
        """
        first_error: Exception | None = None

        await self._events.emit_module_shutdown()
        await self._events.emit_before_shutdown()

        ordered = self._registry.graph.topological_sort()
        levels = self._registry.graph.compute_boot_levels(ordered)

        async with self._lock:
            for level in reversed(levels):
                to_shutdown = [
                    p
                    for p in level
                    if p.name in self._boot_order and p.state == ProviderState.BOOTED
                ]
                if not to_shutdown:
                    continue

                async def _shutdown_one(p: Provider) -> None:
                    try:
                        t0 = time.perf_counter()
                        await p.shutdown()
                        p._state = ProviderState.SHUTDOWN
                        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                        logger.debug(
                            "provider.shutdown",
                            provider=p.name,
                            elapsed_ms=elapsed_ms,
                        )
                    except Exception as exc:  # noqa: BLE001 — all providers shut down even if some fail
                        logger.exception(
                            "provider.shutdown.error",
                            provider=p.name,
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                        nonlocal first_error
                        if first_error is None:
                            first_error = exc

                if len(to_shutdown) == 1:
                    await _shutdown_one(to_shutdown[0])
                else:
                    await asyncio.gather(*[_shutdown_one(p) for p in to_shutdown])

            self._boot_order.clear()

        await self._events.emit_application_shutdown()

        if first_error is not None:
            raise RuntimeError(
                f"Provider shutdown failed: {first_error}",
            ) from first_error

    async def _inject_provider_config(
        self, provider: Provider, registrar: ContainerRegistrarProtocol
    ) -> None:
        """Inject config into provider.config before register() is called.

        If the provider declares both config_key and config_model, resolves
        QuadkitConfig from the container and calls get_section() to populate
        provider.config. Providers that declare neither attribute are unaffected.

        Args:
            provider: The provider about to be registered.
            registrar: The container registrar (must also implement resolve_optional).

        Raises:
            ConfigurationError: If config_key is set but config_model is not,
                or if QuadkitConfig is not registered in the container.
        """
        if provider.config_key is None:
            return

        if getattr(provider, "_config_from_factory", False):
            return

        if provider.config_model is None:
            raise ConfigurationError(
                f"Provider {provider.name!r} declared config_key={provider.config_key!r} "
                f"but no config_model — both must be set together"
            )

        from quadkit.config.main import QuadkitConfig

        resolve_optional = getattr(registrar, "resolve_optional", None)
        if resolve_optional is None:
            raise ConfigurationError(
                f"Provider {provider.name!r} declared config_key={provider.config_key!r} "
                f"but the container does not support resolve_optional"
            )

        qk_config: QuadkitConfig | None = await resolve_optional(QuadkitConfig)
        if qk_config is None:
            raise ConfigurationError(
                f"Provider {provider.name!r} declared config_key={provider.config_key!r} "
                f"but QuadkitConfig is not registered in the container"
            )

        provider.config = qk_config.get_section(
            provider.config_key, provider.config_model
        )

    def _find_module_class(self, provider: Provider) -> type | None:
        """Find the module class that owns this provider in the compiled graph.

        Args:
            provider: The provider instance being booted.

        Returns:
            The module class that owns this provider, or None if not found.
        """
        compiled_graph = self._registry._compiled_graph
        if compiled_graph is None:
            return None
        for entry in compiled_graph.provider_order:
            if entry.is_instance:
                if entry.provider is provider:
                    return entry.module_class
            elif entry.provider is type(provider):
                return entry.module_class
        return None

    def _validate_modules(self) -> list[str]:
        """Validate module import/export declarations.

        Returns:
            List of error messages for missing module exports.
        """
        issues = []
        all_exports: dict[type, str] = {}

        for provider in self._registry._providers.values():
            module_meta = getattr(provider.__class__, "__quadkit_module__", None)
            if not module_meta:
                continue
            for export_type in module_meta.exports:
                all_exports[export_type] = module_meta.name

        for provider in self._registry._providers.values():
            module_meta = getattr(provider.__class__, "__quadkit_module__", None)
            if not module_meta:
                continue
            for import_type in module_meta.imports:
                if import_type not in all_exports:
                    issues.append(
                        f"Module '{module_meta.name}' imports {import_type.__name__} "
                        f"but no module exports it"
                    )

        return issues

    async def _boot_one(
        self, provider: Provider, container: BootContainerProtocol
    ) -> None:
        """Boot a single provider with module context for visibility enforcement.

        Sets the module context ContextVar before calling provider.boot() to enable
        visibility checking during dependency resolution. The context is guaranteed
        to be cleared via try/finally even if boot fails.

        For non-required providers, boot failures are logged as warnings and do not
        halt the boot sequence. Required provider failures trigger rollback.

        Args:
            provider: Provider instance to boot. Must be in REGISTERED state.
            container: Container for boot phase (resolve and register).

        Raises:
            RuntimeError: If provider is not in REGISTERED state.
            TimeoutError: If provider.boot_timeout is set and exceeded.
        """
        if provider.state == ProviderState.BOOTED:
            return

        if provider.state != ProviderState.REGISTERED:
            raise RuntimeError(
                f"Provider {provider.name!r} cannot boot: "
                f"state is {provider.state.value!r}, expected 'registered'.",
            )

        module_class = self._find_module_class(provider)
        tokens = set_module_context(module_class, self._registry._compiled_graph)
        t0 = time.perf_counter()
        try:
            if provider.boot_timeout is not None:
                await asyncio.wait_for(
                    provider.boot(container),
                    timeout=provider.boot_timeout,
                )
            else:
                await provider.boot(container)
        except Exception as exc:  # noqa: BLE001 — required/non-required contract must hold for any error type
            await provider.on_error(exc, "boot")
            if not provider.required:
                logger.warning(
                    "provider.boot.non_required_failed",
                    provider=provider.name,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                return
            raise
        finally:
            clear_module_context(tokens)

        provider._state = ProviderState.BOOTED
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        self._boot_order.append(provider.name)
        logger.debug(
            "provider.booted",
            provider=provider.name,
            elapsed_ms=elapsed_ms,
        )
        await self._events.emit_module_init(provider)


__all__ = ["LifecycleManager"]
