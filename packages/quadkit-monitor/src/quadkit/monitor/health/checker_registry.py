from __future__ import annotations

from typing import Any

from quadkit.monitor.health.cached import CachedHealthChecker


class HealthCheckerRegistry:
    """Singleton-style registry for named :class:`CachedHealthChecker` instances.

    Manages the lifecycle of zero or more named checkers.  The registry is
    registered as a container singleton by
    :class:`~quadkit.monitor.di.provider.MonitorProvider`; application code
    should resolve it via constructor injection rather than instantiating it
    directly.

    Lifecycle::

        # At application startup — wired by MonitorProvider automatically.
        registry = HealthCheckerRegistry()
        checker = registry.get_or_create("api", db_provider=db)

        # At application shutdown — MonitorProvider calls this.
        await registry.cleanup()
    """

    def __init__(self) -> None:
        self._checkers: dict[str, CachedHealthChecker] = {}

    def get_or_create(
        self,
        key: str = "default",
        db_provider: Any = None,
        cache_backend: Any = None,
        cache_ttl: float = 5.0,
        check_timeout: float = 2.0,
    ) -> CachedHealthChecker:
        """Return the named checker, creating it if it does not yet exist.

        Subsequent calls with the same *key* always return the same instance
        regardless of *db_provider*, *cache_ttl*, or *check_timeout* — those
        arguments are ignored after the first call for a given key.

        Args:
            key: Logical name for this checker.  Use distinct keys to manage
                independent groups of health checks (e.g. ``"api"`` vs
                ``"worker"``).
            db_provider: Optional database provider injected into the checker
                for database connectivity verification.
            cache_backend: Optional cache backend injected into the checker
                for cache connectivity verification.
            cache_ttl: Seconds to cache the last health-check result before
                re-running the underlying checks.  Defaults to ``5.0``.
            check_timeout: Per-check execution timeout in seconds.  Defaults
                to ``2.0``.

        Returns:
            The :class:`CachedHealthChecker` registered under *key*.
        """
        if key not in self._checkers:
            self._checkers[key] = CachedHealthChecker(
                cache_ttl=cache_ttl,
                check_timeout=check_timeout,
                db_provider=db_provider,
                cache_backend=cache_backend,
            )
        return self._checkers[key]

    def get_checker(self, key: str = "default") -> CachedHealthChecker | None:
        """Return the checker registered under *key*, or ``None`` if absent.

        Args:
            key: The logical name used when the checker was created.

        Returns:
            The :class:`CachedHealthChecker` or ``None``.
        """
        return self._checkers.get(key)

    def list_checkers(self) -> dict[str, CachedHealthChecker]:
        """Return a snapshot of all registered checkers keyed by name.

        Returns:
            A shallow copy of the internal registry mapping.
        """
        return self._checkers.copy()

    async def cleanup(self) -> None:
        """Stop background refresh tasks for every checker and clear the registry.

        Called automatically by :class:`~quadkit.monitor.di.provider.MonitorProvider`
        during application shutdown.  It is safe to call multiple times.
        """
        # noqa: RUF100  — not a duplicate; stop is on the checker, not self
        for checker in self._checkers.values():
            await checker.stop_background_refresh()
        self._checkers.clear()


async def get_health_checker(
    db_provider: Any = None, context: Any | None = None
) -> CachedHealthChecker:
    """Get the default health checker instance."""
    from quadkit.di.resolution.context import get_resolver

    resolver = get_resolver(context)
    if resolver is None:
        raise ValueError("Could not find resolver")

    registry = await resolver.resolve(HealthCheckerRegistry)
    return registry.get_or_create(db_provider=db_provider)
