"""Resilience backends for the Quadkit cache package.

Provides Redis-backed state storage for resilience primitives (e.g. circuit
breakers) that require distributed, cross-process state.

Usage::

    from quadkit.cache.backends.redis.resilience import RedisCircuitBreakerBackend
    from the optional provider module import CircuitBreakerRegistry

    backend = RedisCircuitBreakerBackend(
        redis_url="redis://localhost:6379",
        key_prefix="myapp:cb:",
    )
    registry = CircuitBreakerRegistry(backend=backend)
"""

from __future__ import annotations

from typing import Any

from quadkit.cache.backends.redis.circuit import (
    CircuitBreakerBackend,
    CircuitBreakerState,
    CircuitState,
)


class RedisCircuitBreakerBackend:
    """Redis backend for distributed circuit breaker state.

    Suitable for multi-process deployments where circuit breaker state must
    be shared across containers or workers.  Implements
    :class:`~the optional provider module`.

    Args:
        redis_url: Redis connection URL.
        key_prefix: Prefix applied to all Redis keys.
        ttl: Time-to-live for state entries (seconds).

    Example::

        backend = RedisCircuitBreakerBackend(
            redis_url="redis://localhost:6379",
            key_prefix="quadkit:cb:",
        )
        registry = CircuitBreakerRegistry(backend=backend)
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "quadkit:cb:",
        ttl: int = 3600,
    ) -> None:
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._ttl = ttl
        self._redis: Any = None

    async def _get_redis(self) -> Any:
        """Lazy-initialise the Redis client."""
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self._redis_url)
        return self._redis

    async def get_state(self, name: str) -> CircuitBreakerState | None:
        """Return circuit breaker state stored in Redis, or ``None``."""
        from quadkit import serialization as json

        redis = await self._get_redis()
        key = f"{self._key_prefix}{name}"
        data = await redis.get(key)
        if data is None:
            return None

        d = json.loads(data)
        return CircuitBreakerState(
            name=d["name"],
            state=CircuitState(d["state"]),
            failure_count=d["failure_count"],
            success_count=d["success_count"],
            last_failure_time=d.get("last_failure_time"),
            last_success_time=d.get("last_success_time"),
            last_state_change=d["last_state_change"],
        )

    async def set_state(self, name: str, state: CircuitBreakerState) -> None:
        """Persist circuit breaker *state* under *name* in Redis."""
        from quadkit import serialization as json

        redis = await self._get_redis()
        key = f"{self._key_prefix}{name}"
        payload = {
            "name": state.name,
            "state": state.state.value,
            "failure_count": state.failure_count,
            "success_count": state.success_count,
            "last_failure_time": state.last_failure_time,
            "last_success_time": state.last_success_time,
            "last_state_change": state.last_state_change,
        }
        await redis.set(key, json.dumps(payload), ex=self._ttl)

    async def delete_state(self, name: str) -> None:
        """Remove the stored state for *name* from Redis."""
        redis = await self._get_redis()
        await redis.delete(f"{self._key_prefix}{name}")


__all__ = [
    "CircuitBreakerBackend",
    "RedisCircuitBreakerBackend",
]
