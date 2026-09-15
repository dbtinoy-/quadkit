"""Lifecycle protocols for Quadkit Framework.

These protocols allow providers and services to hook into framework
lifecycle events such as initialization and shutdown.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OnModuleInitProtocol(Protocol):
    """Provider implements this to run initialization logic.

    Called once when the provider is first booted, BEFORE other providers
    that depend on it.

    Behavioral Contract:
        - Implementers MUST be idempotent — calling ``on_module_init()``
          twice MUST NOT produce side effects or raise.
        - Implementers SHOULD complete quickly — blocking here delays
          the entire boot sequence.
        - Implementers MUST NOT resolve services from other providers
          that have not yet been booted.
    """

    async def on_module_init(self) -> None:
        """Initialize provider after registration but before other providers boot."""
        ...


@runtime_checkable
class OnApplicationBootstrapProtocol(Protocol):
    """Provider implements this to run after application bootstrap.

    Called after ALL providers have been booted successfully.
    At this point every service is fully resolved and available.

    Behavioral Contract:
        - Implementers MUST NOT throw exceptions — doing so indicates
          a fatal application startup failure.
        - Implementers CAN resolve any service from the container.
        - Implementers SHOULD start background tasks, schedulers, or
          listeners here rather than in ``on_module_init()``.
    """

    async def on_application_bootstrap(self) -> None:
        """Run after all providers are booted."""
        ...


@runtime_checkable
class OnBeforeShutdownProtocol(Protocol):
    """Provider implements this to run before shutdown begins.

    Called before any provider's ``shutdown()`` method is invoked.
    Use this to drain queues, finish in-flight requests, or save state.

    Behavioral Contract:
        - Implementers MUST complete within a reasonable timeout.
        - Implementers SHOULD NOT start new work — only finish existing work.
        - Implementers MUST NOT throw exceptions.
    """

    async def on_before_shutdown(self, signal: str | None = None) -> None:
        """Run before shutdown begins."""
        ...


@runtime_checkable
class OnApplicationShutdownProtocol(Protocol):
    """Provider implements this to run after shutdown completes.

    Called after ALL providers have been shut down.
    Use this for final cleanup like closing log files or flushing metrics.

    Behavioral Contract:
        - Implementers MUST NOT resolve services — the container is
          already disposed at this point.
        - Implementers MUST NOT throw exceptions.
        - Implementers SHOULD release any remaining OS resources.
    """

    async def on_application_shutdown(self, signal: str | None = None) -> None:
        """Run after all providers are shut down."""
        ...


@runtime_checkable
class GracefulShutdownProtocol(Protocol):
    """Standard protocol for services that support graceful shutdown.

    Any service that holds background tasks, open connections, or in-flight
    work SHOULD implement this protocol.  The framework will call
    ``shutdown()`` on all registered services during teardown.

    Behavioral Contract:
        - ``shutdown()`` MUST be idempotent — calling it twice is safe.
        - ``shutdown()`` SHOULD complete within a reasonable timeout.
        - ``shutdown()`` MUST NOT raise exceptions.
        - ``shutdown()`` SHOULD release all held resources (tasks, connections,
          file handles) before returning.
    """

    async def shutdown(self) -> None:
        """Request graceful shutdown and wait for completion."""
        ...


@runtime_checkable
class OnConfigReloadProtocol(Protocol):
    """Lifecycle hook called when application configuration is reloaded at runtime.

    Services that hold configuration-derived state (e.g., connection pools,
    caches, rate-limiters) SHOULD implement this protocol to react to live
    config changes without requiring a full restart.

    Behavioral Contract:
        - ``on_config_reload`` MUST be idempotent.
        - ``on_config_reload`` SHOULD complete quickly; defer heavy work to a background task.
        - ``on_config_reload`` MUST NOT raise exceptions; log and absorb errors.

    Example::

        class RedisCache(OnConfigReloadProtocol):
            async def on_config_reload(self, new_config: Any) -> None:
                self._ttl = new_config.cache.default_ttl
    """

    async def on_config_reload(self, new_config: Any) -> None:
        """React to a live configuration change.

        Args:
            new_config: The new application configuration object.
        """
        ...


__all__ = [
    "GracefulShutdownProtocol",
    "OnApplicationBootstrapProtocol",
    "OnApplicationShutdownProtocol",
    "OnBeforeShutdownProtocol",
    "OnConfigReloadProtocol",
    "OnModuleInitProtocol",
]
