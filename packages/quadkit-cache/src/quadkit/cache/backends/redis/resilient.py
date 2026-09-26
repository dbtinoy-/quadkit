"""Resilient Redis cache backend — decorator composition (D3.3).

Replaces the monolithic ``RedisCircuitBreakerBackend`` with a clean decorator
that composes any :class:`~quadkit.cache.backends.redis.backend.RedisCacheBackend`
with a :class:`~quadkit.contracts.infra.resilience.CircuitBreakerProtocol` injected
from the DI container.

This approach follows the decorator pattern: behaviour is layered at wiring
time rather than baked into a single class, making the resilience strategy
swappable without subclassing.

Usage::

    from quadkit.cache.backends.redis.backend import RedisCacheBackend
    from quadkit.cache.backends.redis.resilient import ResilientRedisCacheBackend

    # Injected from the DI container
    breaker: CircuitBreakerProtocol = await container.resolve(CircuitBreakerProtocol)

    backend = ResilientRedisCacheBackend(
        inner=RedisCacheBackend(url="redis://localhost:6379"),
        breaker=breaker,
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
    from quadkit.contracts.infra.resilience import CircuitBreakerProtocol

logger = get_logger(__name__)


class ResilientRedisCacheBackend:
    """Composes a ``CacheBackendProtocol`` with a ``CircuitBreakerProtocol``.

    Every cache operation is routed through the circuit breaker.  When the
    breaker is open (too many recent failures) operations fail fast without
    hitting Redis, preventing cascade failures.

    Implements :class:`~quadkit.contracts.cache.protocols.CacheBackendProtocol`
    structurally so it can be registered with the same container key.

    Args:
        inner: The underlying cache backend (e.g. ``RedisCacheBackend``).
        breaker: Circuit breaker instance resolved from the DI container.
    """

    def __init__(
        self,
        inner: CacheBackendProtocol,
        breaker: CircuitBreakerProtocol,
    ) -> None:
        self._inner = inner
        self._breaker = breaker

    async def get(self, key: str) -> Any:
        """Get a value — routed through the circuit breaker."""
        from quadkit.contracts.infra.cache.exceptions import CacheError
        from quadkit.result import Err

        try:
            return await self._breaker.call(self._inner.get, key)
        except Exception as e:  # noqa: BLE001
            logger.debug("cache_get_circuit_open", key=key)
            return Err(CacheError(f"Circuit breaker error: {e}"))

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> Any:
        """Set a value — routed through the circuit breaker."""
        from quadkit.contracts.infra.cache.exceptions import CacheError
        from quadkit.result import Err

        try:
            return await self._breaker.call(self._inner.set, key, value, ttl)
        except Exception as e:  # noqa: BLE001
            logger.debug("cache_set_circuit_open", key=key)
            return Err(CacheError(f"Circuit breaker error: {e}"))

    async def delete(self, key: str) -> Any:
        """Delete a value — routed through the circuit breaker."""
        from quadkit.contracts.infra.cache.exceptions import CacheError
        from quadkit.result import Err

        try:
            return await self._breaker.call(self._inner.delete, key)
        except Exception as e:  # noqa: BLE001
            logger.debug("cache_delete_circuit_open", key=key)
            return Err(CacheError(f"Circuit breaker error: {e}"))

    async def exists(self, key: str) -> Any:
        """Check existence — routed through the circuit breaker."""
        from quadkit.contracts.infra.cache.exceptions import CacheError
        from quadkit.result import Err

        try:
            return await self._breaker.call(self._inner.exists, key)
        except Exception as e:  # noqa: BLE001
            return Err(CacheError(f"Circuit breaker error: {e}"))

    async def clear(self) -> Any:
        """Clear all keys — routed through the circuit breaker."""
        from quadkit.contracts.infra.cache.exceptions import CacheError
        from quadkit.result import Err

        try:
            return await self._breaker.call(self._inner.clear)
        except Exception as e:  # noqa: BLE001
            logger.debug("cache_clear_circuit_open")
            return Err(CacheError(f"Circuit breaker error: {e}"))

    async def get_many(self, keys: list[str]) -> Any:
        from quadkit.contracts.infra.cache.exceptions import CacheError
        from quadkit.result import Err

        try:
            return await self._breaker.call(self._inner.get_many, keys)
        except Exception as e:  # noqa: BLE001
            return Err(CacheError(f"Circuit breaker error: {e}"))

    async def set_many(self, items: dict[str, Any], ttl: int | None = None) -> Any:
        from quadkit.contracts.infra.cache.exceptions import CacheError
        from quadkit.result import Err

        try:
            return await self._breaker.call(self._inner.set_many, items, ttl)
        except Exception as e:  # noqa: BLE001
            return Err(CacheError(f"Circuit breaker error: {e}"))

    async def delete_many(self, keys: list[str]) -> Any:
        from quadkit.contracts.infra.cache.exceptions import CacheError
        from quadkit.result import Err

        try:
            return await self._breaker.call(self._inner.delete_many, keys)
        except Exception as e:  # noqa: BLE001
            return Err(CacheError(f"Circuit breaker error: {e}"))

    async def delete_pattern(self, pattern: str) -> Any:
        from quadkit.contracts.infra.cache.exceptions import CacheError
        from quadkit.result import Err

        try:
            return await self._breaker.call(self._inner.delete_pattern, pattern)
        except Exception as e:  # noqa: BLE001
            return Err(CacheError(f"Circuit breaker error: {e}"))

    async def health_check(self, timeout: float = 5.0) -> Any:
        from quadkit.contracts.core.health import HealthCheckResult, HealthStatus

        try:
            return await self._breaker.call(self._inner.health_check, timeout)
        except Exception as e:  # noqa: BLE001
            return HealthCheckResult(
                component="cache:resilient", status=HealthStatus.UNHEALTHY, error=str(e)
            )


__all__ = ["ResilientRedisCacheBackend"]
