"""Middleware registry for named, prioritized middleware management.

Provides a registry-based approach to middleware management, allowing
middleware to be registered by name and applied in priority order.

Example::

    from quadkit.middleware.core.registry import MiddlewareRegistry

    registry = MiddlewareRegistry()
    registry.register("timing", TimingMiddleware(), priority=10)
    registry.register("logging", LoggingMiddleware(), priority=20)
    registry.register("auth", AuthMiddleware(), priority=30)

    # Get all middleware in priority order:
    for mw in registry.all():
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.middleware.config import MiddlewareConfig
    from quadkit.middleware.core.chain import MiddlewareChain

from quadkit.contracts.exceptions import RegistryAlreadyExistsError
from quadkit.primitives.registry import Registry


class MiddlewareRegistry(Registry[str, tuple[int, Any]]):
    """Named middleware registry with priority ordering.

    Inherits from ``Registry`` with priority support for ordering middleware
    by priority. Middleware is stored by name and retrieved in ascending
    priority order (lower number = earlier execution).

    The registry is thread-safe through the base ``Registry`` implementation.

    Example::

        registry = MiddlewareRegistry()
        registry.register("auth", AuthMiddleware(), priority=10)
        registry.register("logging", LoggingMiddleware(), priority=20)

        # Returns middleware in priority order (auth first, then logging)
        middleware_list = registry.all()
    """

    def __init__(self) -> None:
        """Initialize the middleware registry with priority ordering."""
        super().__init__(
            name="MiddlewareRegistry",
            allow_overwrite=False,
            priority_key=lambda entry: entry[0],
        )

    def register(  # type: ignore[override]
        self,
        name: str,
        middleware: Any,
        *,
        priority: int = 50,
    ) -> None:
        """Register a named middleware.

        Args:
            name: Unique name for this middleware.
            middleware: The middleware instance.
            priority: Execution order - lower values run first. Default 50.

        Raises:
            ValueError: If a middleware with the same name is already registered.
        """
        # Store as tuple (priority, middleware) for priority-based ordering
        entry = (priority, middleware)
        # Use the base register method
        try:
            super().register(name, entry)
        except RegistryAlreadyExistsError as e:
            # Convert base registry errors to ValueError for backward compatibility
            msg = f"Middleware '{name}' is already registered"
            raise ValueError(msg) from e

    def unregister(self, name: str) -> Any:
        """Remove and return a named middleware.

        Args:
            name: The middleware name to remove.

        Returns:
            The removed middleware instance.

        Raises:
            KeyError: If no middleware with the given name is registered.
        """
        entry = super().unregister(name)
        if entry is None:
            msg = f"No middleware registered with name '{name}'"
            raise KeyError(msg)
        return entry[1]  # Return just the middleware, not the tuple

    def get(self, name: str) -> Any:  # type: ignore[override]
        """Retrieve a named middleware.

        Args:
            name: The middleware name to look up.

        Returns:
            The middleware instance.

        Raises:
            KeyError: If no middleware with the given name is registered.
        """
        entry: tuple[int, Any] | None = super().get(name)
        if entry is None:
            msg = f"No middleware registered with name '{name}'"
            raise KeyError(msg)
        return entry[1]

    def all(self) -> list[Any]:
        """Return all middleware in priority order.

        Returns:
            List of middleware instances sorted by ascending priority.
        """
        # Use values_ordered to get entries sorted by priority
        entries = self.values_ordered()
        return [entry[1] for entry in entries]  # Extract middleware from tuples

    def has(self, name: str) -> bool:
        """Check if a middleware with the given name is registered."""
        return super().has(name)

    def names(self) -> list[str]:
        """Return a sorted list of registered middleware names."""
        return sorted(self.keys())

    def build_chain(self) -> MiddlewareChain:
        """Build a :class:`MiddlewareChain` from all registered middleware.

        Returns middleware in ascending priority order (lower priority number
        executes first).

        Returns:
            A new :class:`MiddlewareChain` containing all registered middleware.

        Example::

            registry = MiddlewareRegistry()
            registry.register("auth", AuthMiddleware(), priority=10)
            registry.register("logging", LoggingMiddleware(), priority=20)
            chain = registry.build_chain()
            result = await chain.execute(request)
        """
        from quadkit.middleware.core.chain import MiddlewareChain

        return MiddlewareChain(self.all())

    @classmethod
    def _default_entries(cls) -> dict[str, tuple[int, Any]]:
        """Declare the built-in infrastructure middleware (priority, instance)."""
        from quadkit.middleware.builtins import (
            CorrelationIdMiddleware,
            LoggingMiddleware,
            TimingMiddleware,
        )

        return {
            "logging": (10, LoggingMiddleware()),
            "correlation_id": (20, CorrelationIdMiddleware()),
            "timing": (90, TimingMiddleware()),
        }

    @classmethod
    def with_defaults(cls) -> MiddlewareRegistry:
        """Pre-populate with standard infrastructure middleware."""
        registry = cls()
        for name, (priority, middleware) in cls._default_entries().items():
            registry.register(name, middleware, priority=priority)
        return registry

    @classmethod
    def with_resilience(
        cls,
        config: MiddlewareConfig | None = None,
        catch: type[Exception] | tuple[type[Exception], ...] = (
            ConnectionError,
            TimeoutError,
        ),
    ) -> MiddlewareRegistry:
        """Defaults plus resilience middlewares built from *config*.

        Every ``MiddlewareConfig`` resilience field has a consumer here:
        ``default_retry_count``/``default_retry_delay`` -> RetryMiddleware,
        ``circuit_failure_threshold``/``circuit_recovery_timeout`` ->
        CircuitBreakerMiddleware, ``rate_limit_max_requests``/
        ``rate_limit_window`` -> RateLimiterMiddleware,
        ``default_timeout`` -> TimeoutMiddleware.

        Args:
            config: Middleware defaults; falls back to ``MiddlewareConfig()``.
            catch: Exceptions RetryMiddleware retries (connection-level by
                default; widen deliberately, e.g. to ``Exception``).
        """
        from quadkit.middleware.builtins.resilience import (
            CircuitBreakerMiddleware,
            RateLimiterMiddleware,
            RetryMiddleware,
            TimeoutMiddleware,
        )
        from quadkit.middleware.config import MiddlewareConfig

        cfg = config or MiddlewareConfig()
        registry = cls.with_defaults()
        registry.register(
            "retry",
            RetryMiddleware(
                catch,
                max_retries=cfg.default_retry_count,
                delay=cfg.default_retry_delay,
            ),
            priority=30,
        )
        registry.register(
            "circuit_breaker",
            CircuitBreakerMiddleware(
                failure_threshold=cfg.circuit_failure_threshold,
                recovery_timeout=cfg.circuit_recovery_timeout,
            ),
            priority=40,
        )
        registry.register(
            "rate_limiter",
            RateLimiterMiddleware(
                max_requests=cfg.rate_limit_max_requests,
                window_seconds=cfg.rate_limit_window,
            ),
            priority=50,
        )
        registry.register(
            "timeout",
            TimeoutMiddleware(timeout=cfg.default_timeout),
            priority=60,
        )
        return registry

    def __repr__(self) -> str:
        entries = [(name, entry[0]) for name, entry in self._items.items()]
        parts = ", ".join(
            f"{n}(priority={p})" for n, p in sorted(entries, key=lambda x: x[1])
        )
        return f"MiddlewareRegistry([{parts}])"


__all__ = [
    "MiddlewareRegistry",
]
