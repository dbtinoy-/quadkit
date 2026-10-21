"""Application class — the composition root for Quadkit."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from enum import StrEnum
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, TypeVar, cast

from quadkit.app.constants import DEFAULT_SHUTDOWN_TIMEOUT
from quadkit.app.exceptions import AppShutdownError
from quadkit.app.health_probes import HealthProbeMixin
from quadkit.app.invoker import Invoker
from quadkit.app.lifecycle import ApplicationLifecycle
from quadkit.app.pipeline import MiddlewarePipeline
from quadkit.app.secrets import SecretsMixin
from quadkit.config import QuadkitConfig
from quadkit.contracts.core import MiddlewarePipelineProtocol, MiddlewareProtocol
from quadkit.contracts.core.config import ConfigProtocol
from quadkit.contracts.core.health import AggregateHealthResult, HealthCheckCategory
from quadkit.di.container import Container
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.logging import get_logger
from quadkit.logging.configurator import apply_config as _apply_logging_config

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.di.module.dynamic import DynamicModule
    from quadkit.di.module.graph import CompiledModuleGraph
    from quadkit.di.provider import Provider
    from quadkit.logging import LoggerProtocol

T = TypeVar("T")


class AppState(StrEnum):
    """Application lifecycle states."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


class Application(SecretsMixin, HealthProbeMixin):
    """The composition root.

    Usage::

        async with Application.boot(providers=[MyProvider()]) as app:
            # resolve Invoker from the container for entry-point injection
            from quadkit.app.invoker import Invoker
            invoker = await app.container.resolve(Invoker)
            await invoker.invoke(main)

    Or for long-running processes::

        app = Application()
        app.add_provider(MyProvider())
        from quadkit.app import run_application
        await run_application(app)
    """

    def __init__(
        self,
        name: str = "quadkit-app",
        config: QuadkitConfig | None = None,
    ) -> None:
        self.name = name
        self._state = AppState.CREATED
        self._container = Container()
        self._container.singleton(type(self), self)
        self._orchestrator: ProviderOrchestrator = ProviderOrchestrator(self._container)

        self._config = config or QuadkitConfig.from_env_profile()
        self._container.singleton(QuadkitConfig, self._config)
        self._container.singleton(ConfigProtocol, self._config)

        # Configure logging immediately so all module-level get_logger()
        # calls during subsequent imports use the correct filtering wrapper.
        _apply_logging_config(self._config.logging, service_name=self.name)
        self._logger: LoggerProtocol = get_logger(name)

        self._middleware: MiddlewarePipeline = MiddlewarePipeline()
        self._container.singleton(MiddlewarePipelineProtocol, self._middleware)

        self._invoker = Invoker(self._container, self._middleware)
        self._container.singleton(Invoker, self._invoker)

        self._modules: list[type | DynamicModule] = []

        self._lifecycle = ApplicationLifecycle(
            container=self._container,
            orchestrator=self._orchestrator,
            config=self._config,
            logger=self._logger,
            app_name=self.name,
        )

        # Secrets registered by the app for boot-time validation.
        # Populated via register_secrets() and register_secrets_from_store();
        # validated in start().
        self._registered_secrets: dict[str, str] = {}
        self._secrets_from_stores: list[
            tuple[Any, list[str]]
        ] = []  # list[tuple[SecretStoreProtocol, list[str]]]
        self._secrets_policy: Any | None = None  # SecretsPolicy | None

    # -- Properties --------------------------------------------------------

    @property
    def state(self) -> AppState:
        """Current application state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if application is running."""
        return self._state == AppState.RUNNING

    @property
    def logger(self) -> LoggerProtocol:
        """Get the application logger."""
        return self._logger

    @property
    def config(self) -> QuadkitConfig:
        """Application configuration."""
        return self._config

    @property
    def container(self) -> Container:
        """DI container."""
        return self._container

    @property
    def module_graph(self) -> CompiledModuleGraph | None:
        """The compiled module graph, or ``None`` before compilation.

        Read-only view of what the boot sequence compiled: every module with
        its providers, imports, and fully expanded exports. It exists so
        boot-time guards can assert that what a module *declares* it exports is
        what the container can actually resolve — the failure this graph is
        otherwise blind to, because an export that nothing resolves during
        boot only fails later, at ``QK_ERR_DI_004`` on first use, or never.

        Returns:
            The compiled graph, or ``None`` when the application has not been
            compiled yet.
        """
        return self._orchestrator.compiled_graph

    @property
    def providers(self) -> list[Provider]:
        """Get all registered providers."""
        return list(self._orchestrator.providers)

    # -- Secrets registration ----------------------------------------------

    # -- Middleware registration -------------------------------------------

    def add_middleware(self, middleware: MiddlewareProtocol[Any, Any]) -> None:
        """Add a middleware to the application."""
        # MiddlewarePipeline is immutable: add() returns a NEW pipeline, so
        # the old instance (held by the container singleton and the Invoker)
        # must be rebound to keep middleware resolution consistent.
        self._middleware = self._middleware.add(middleware)
        self._container.bind(MiddlewarePipelineProtocol, self._middleware)  # type: ignore[type-abstract]
        self._invoker._middleware = self._middleware

    # -- Provider registration ---------------------------------------------

    def add_provider(self, provider: Provider) -> None:
        """Add a provider to be orchestrated.

        Must be called before ``start()``.
        """
        if self._state != AppState.CREATED:
            raise RuntimeError(
                f"Cannot add provider after boot. State: {self._state.value}",
            )
        # Orchestrator will recursively add any sub-providers
        self._orchestrator.add(provider)

    def add_providers(self, providers: list[Provider]) -> None:
        """Add multiple providers. Must be called before ``start()``."""
        for provider in providers:
            self.add_provider(provider)

    def discover_providers(self, *packages: str) -> None:
        """Discover and add Provider subclasses from packages.

        Scans each package recursively for :class:`~quadkit.di.provider.Provider`
        subclasses with a no-argument constructor and registers them.

        Also discovers ``@injectable`` / ``@singleton`` decorated classes and
        schedules them for auto-registration into the container during boot.

        Convention: place providers in ``<module>/provider.py`` or
        ``<module>/providers/`` — any file is scanned.

        Args:
            *packages: Dotted Python package paths to scan, e.g.
                ``"my_platform.modules"``.

        Example::

            app.discover_providers("my_platform.modules", "my_platform.infrastructure")
        """
        from quadkit.app.discovery import discover_injectables, discover_providers

        for provider in discover_providers(list(packages)):
            self.add_provider(provider)

        # Auto-register @injectable / @singleton classes via a thin synthetic provider
        injectables = discover_injectables(list(packages))
        if injectables:
            from quadkit.app.injectable_provider import InjectableAutoProvider

            self.add_provider(InjectableAutoProvider(injectables))

    # -- Module registration -----------------------------------------------

    def add_module(self, module: type | Any) -> None:
        """Add a module to the application.

        Modules organize providers and define visibility boundaries.
        Must be called before ``start()``.
        """
        if self._state != AppState.CREATED:
            raise RuntimeError(
                f"Cannot add_module after boot. State: {self._state.value}",
            )
        self._modules.append(module)

    def add_modules(self, modules: list[type | Any]) -> None:
        """Add multiple modules. Must be called before ``start()``."""
        for mod in modules:
            self.add_module(mod)

    def discover_modules(
        self,
        *,
        entry_point_group: str = "quadkit.modules",
        directories: list[str | Path] | None = None,
        enabled: list[str] | None = None,
        disabled: list[str] | None = None,
    ) -> None:
        """Discover Module classes and register them with this application.

        Scans importlib.metadata entry points and optionally filesystem
        directories. Each discovered Module is passed to ``add_module()``,
        ensuring it flows through ``CompiledModuleGraph`` during ``start()``.

        Args:
            entry_point_group: Entry-point group to scan. Default "quadkit.modules".
            directories: Extra filesystem directories to scan.
            enabled: Allowlist of module names (empty = all allowed).
            disabled: Denylist of module names to skip.

        Example::

            app.discover_modules()
            app.discover_modules(directories=["./plugins"], disabled=["dev-only"])
        """
        from quadkit.app.discovery import (
            discover_modules_from_directories,
            discover_modules_from_entry_points,
        )

        discovered = discover_modules_from_entry_points(entry_point_group)

        if directories:
            dir_paths = [Path(d) for d in directories]
            for name, cls in discover_modules_from_directories(dir_paths).items():  # type: ignore[arg-type]
                if name not in discovered:
                    discovered[name] = cls

        disabled_set = set(disabled or [])
        enabled_set = set(enabled or [])

        for name, module_cls in discovered.items():
            if name in disabled_set:
                continue
            if enabled_set and name not in enabled_set:
                continue
            self.add_module(module_cls)

    # -- Lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        """Boot all providers and start the application.

        Phases:
            0. Validate configuration against the active environment
            1. Emit ``ApplicationStarting`` event
            2. Register all providers with the container
            3. Boot all providers (dependency order, parallel where possible)
            4. Resolve ``EventBusProtocol`` from container for lifecycle events
            5. Emit ``ApplicationStarted`` event

        If any phase fails, already-booted providers are shut down
        and the application moves to STOPPED.

        Raises:
            RuntimeError: If application is not in CREATED state.
            ConfigurationError: If the configuration violates
                environment-specific constraints (e.g. ``debug=True``
                in production).
        """
        if self._state != AppState.CREATED:
            raise RuntimeError(f"Cannot start: state is {self._state.value}")

        self._state = AppState.STARTING

        try:
            # Phase 0: fail fast on configuration that violates hard
            # constraints for the active environment (e.g. debug=True in
            # production) before any provider boots.
            self._validate_config()

            def _auto_discover_and_compile() -> None:
                if self._config.discovery.auto_discover:
                    cfg = self._config.discovery
                    self.discover_modules(
                        entry_point_group=cfg.entry_point_group,
                        directories=cfg.directories or None,  # type: ignore[arg-type]
                        enabled=cfg.enabled_modules or None,
                        disabled=cfg.disabled_modules or None,
                    )

                if self._modules:
                    from quadkit.di.module.compiler import ModuleCompiler

                    compiler = ModuleCompiler()

                    standalone = self._orchestrator.providers

                    graph = compiler.compile(
                        root_modules=self._modules, standalone_providers=standalone
                    )

                    self._orchestrator.clear_providers()
                    self._orchestrator.set_compiled_graph(graph)
                    for entry in graph.provider_order:
                        # is_instance guarantees a pre-built Provider;
                        # the class branch instantiates before add().
                        p = (
                            cast("Provider", entry.provider)
                            if entry.is_instance
                            else entry.provider()
                        )
                        self._orchestrator.add(p)

            def _validate_secrets() -> None:
                if self._registered_secrets or self._secrets_from_stores:
                    self._validate_secrets()

            await self._lifecycle.boot(
                auto_discover=self._config.discovery.auto_discover,
                discover_callback=_auto_discover_and_compile,
                validate_secrets_callback=_validate_secrets,
            )

            self._state = AppState.RUNNING
            self._lifecycle.print_banner(
                provider_count=len(self._orchestrator.providers),
                module_count=len(self._modules),
            )
        except BaseException:
            self._logger.exception("application.start_failed", name=self.name)
            import traceback

            sys.stderr.write("\n=== APPLICATION BOOT FAILED ===\n")
            traceback.print_exc()
            sys.stderr.write("================================\n")
            sys.stderr.flush()
            try:
                await self._orchestrator.shutdown()
            except RuntimeError as cleanup_err:
                self._logger.exception(
                    "application.cleanup_failed",
                    error=str(cleanup_err),
                )
            self._state = AppState.STOPPED
            raise

    async def stop(self) -> None:
        """Shutdown all providers in reverse order.

        Safe to call multiple times. Handles being called from
        STARTING state (failed boot) as well as RUNNING.

        Emits ``ApplicationStopping`` before shutdown and
        ``ApplicationStopped`` after completion.
        """
        if self._state in (AppState.STOPPED, AppState.CREATED):
            return

        if self._state == AppState.STOPPING:
            self._logger.warning("application.already_stopping", name=self.name)
            return

        self._state = AppState.STOPPING

        from quadkit.app.config.models import AppConfig

        app_config = self._config.get_section("app", AppConfig)
        configured_timeout = app_config.shutdown_timeout
        shutdown_timeout = float(
            configured_timeout
            if configured_timeout is not None
            else DEFAULT_SHUTDOWN_TIMEOUT
        )
        try:
            await asyncio.wait_for(self._lifecycle.shutdown(), timeout=shutdown_timeout)
        except TimeoutError:
            self._logger.error(
                "application.shutdown_timeout",
                name=self.name,
                timeout_seconds=shutdown_timeout,
            )
            raise AppShutdownError(
                f"Application shutdown timed out after {shutdown_timeout:g}s: {self.name}"
            ) from None
        except Exception as err:  # noqa: BLE001 — any shutdown failure becomes AppShutdownError
            self._logger.exception(
                "application.shutdown_error",
                error=str(err),
                name=self.name,
            )
            raise AppShutdownError(f"Application shutdown failed: {self.name}") from err
        finally:
            self._state = AppState.STOPPED

    def _validate_config(self) -> None:
        """Validate configuration against the active environment.

        Delegates to :func:`quadkit.app.config_validation.validate_app_config`;
        error-severity issues (e.g. ``debug=True`` in production) abort the
        boot with :class:`ConfigurationError`.
        """
        from quadkit.app.config_validation import validate_app_config

        validate_app_config(self._config, self._logger)

    async def startup_check(
        self, timeout: float | None = None
    ) -> AggregateHealthResult:
        """Run startup checks for the application."""
        timeout = self._effective_timeout(timeout)
        if self._state != AppState.RUNNING:
            return self._apply_details_policy(
                self._probe_unavailable_result(HealthCheckCategory.STARTUP)
            )
        started = await self._orchestrator.run_startup(timeout)
        started = self._baseline_component(started, HealthCheckCategory.STARTUP)
        return self._apply_details_policy(started)

    # -- Convenience -------------------------------------------------------

    @classmethod
    @asynccontextmanager
    async def boot(
        cls,
        name: str = "quadkit-app",
        providers: list[Provider] | None = None,
        modules: list[Any] | None = None,
        config: QuadkitConfig | None = None,
    ) -> AsyncIterator[Application]:
        """Create, start, yield, and guarantee shutdown.

        Usage::

            async with Application.boot(providers=[...]) as app:
                await app.invoke(main)
        """
        app = cls(name=name, config=config)
        if modules:
            app.add_modules(modules)
        if providers:
            app.add_providers(providers)
        await app.start()
        try:
            yield app
        finally:
            await app.stop()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """ASGI entrypoint. Supports both HTTP and lifespan protocols."""
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return
        handler = getattr(self, "_asgi_handler", None)
        if handler is None and self._state == AppState.CREATED:
            await self.start()
            handler = getattr(self, "_asgi_handler", None)
        if handler is None:
            raise RuntimeError("Application has no ASGI handler registered.")
        await handler(scope, receive, send)

    async def _handle_lifespan(self, receive: Any, send: Any) -> None:
        """Delegate ASGI lifespan handling."""
        from quadkit.app.asgi_lifespan import handle_lifespan

        await handle_lifespan(self, receive, send)

    def __repr__(self) -> str:
        return f"<Application name={self.name!r} state={self._state.value}>"


__all__ = ["AppState", "Application"]
