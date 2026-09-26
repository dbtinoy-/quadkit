"""Redis state store implementation"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import time
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID
import warnings

# redis-py 7.x creates internal `_send_packed_command` coroutines during
# connection establishment that may not be awaited when the connection fails
# (e.g. startup race condition).  This is a known upstream issue; suppress
# the spurious RuntimeWarning so it doesn't pollute application logs.
warnings.filterwarnings(
    "ignore",
    message="coroutine 'AbstractConnection._send_packed_command' was never awaited",
    category=RuntimeWarning,
)

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.logging import get_logger

logger = get_logger(__name__)

RedisError: type[Exception] = Exception
try:
    import redis.asyncio as redis
    from redis.exceptions import RedisError as _RedisError

    RedisError = _RedisError
    HAS_REDIS = True
except ImportError as e:
    redis = None  # type: ignore[assignment]
    RedisError = Exception
    HAS_REDIS = False
    logger.debug("Redis package not available: %s", e, exc_info=True)
except (AttributeError, TypeError, RuntimeError):
    # Unexpected error importing Redis - disable Redis integration and log the error
    redis = None  # type: ignore[assignment]
    RedisError = Exception
    HAS_REDIS = False
    logger.exception("Unexpected error importing redis module")


from quadkit.contracts import (
    StateStoreProtocol,
)
from quadkit.serialization import (
    dumps,
    loads,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable


class RedisDriver:
    """Shared Redis connection logic"""

    def __init__(self, url: str = "", prefix: str = "", client: Any | None = None):
        self.url = url
        self.prefix = prefix
        self._client: Any | None = client

    async def _get_client(self) -> Any:
        """Lazy client initialization with connection health checks."""
        if self._client is not None:
            return self._client
        if not HAS_REDIS:
            raise ImportError(
                "Redis driver is required for Redis-based components. Install with: pip install redis>=4.6.0",
            )
        if self._client is None:
            from_url_fn = redis.from_url
            self._client = cast(
                "Any",
                from_url_fn(
                    self.url,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                    socket_keepalive=True,
                    health_check_interval=30,
                    retry_on_timeout=True,
                ),
            )
        return self._client

    async def close(self) -> None:
        """Close the Redis client, releasing its connection pool."""
        if self._client is not None:
            close_fn = getattr(self._client, "aclose", None) or getattr(
                self._client, "close", None
            )
            if close_fn is not None:
                result = close_fn()
                if hasattr(result, "__await__"):
                    await result
            self._client = None

    def _key(self, key: str) -> str:
        """Apply prefix to key"""
        return f"{self.prefix}{key}" if self.prefix else key

    def _json_encoder(self, obj: Any) -> Any:
        """Enhanced JSON encoder for Python types."""

        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)


class RedisStateStore(RedisDriver, StateStoreProtocol):
    """Redis implementation of StateStoreProtocol"""

    async def get(self, key: str) -> Any | None:
        """Get a value by key"""
        client = await self._get_client()
        val = await client.get(self._key(key))
        return loads(val) if val else None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value with optional TTL"""
        client = await self._get_client()

        # Enhanced serialization with DomainModel support
        from quadkit.domain import DomainModel

        if isinstance(value, DomainModel):
            # DomainModel (dataclass-based)
            value = value.model_dump()
        elif hasattr(value, "json"):
            # Objects with custom JSON serialization
            serialized = value.json()
            await cast("Awaitable[Any]", client.set(self._key(key), serialized, ex=ttl))
            return

        # Standard JSON serialization with enhanced type handling
        serialized = dumps(value, default=self._json_encoder)
        await cast("Awaitable[Any]", client.set(self._key(key), serialized, ex=ttl))

    async def delete(self, key: str) -> bool:
        """Delete a value by key"""
        client = await self._get_client()
        await cast("Awaitable[Any]", client.delete(self._key(key)))
        return True

    async def get_bulk(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values by keys"""
        client = await self._get_client()
        prefixed_keys = [self._key(k) for k in keys]
        values = await client.mget(prefixed_keys)

        result = {}
        for key, value in zip(keys, values, strict=False):
            if value is not None:
                result[key] = loads(value)
        return result

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check the health of the state store"""
        start_time = time.monotonic()
        try:
            client = await self._get_client()
            # Wrap ping in wait_for so internal coroutines are properly
            # cancelled on timeout rather than abandoned.
            await asyncio.wait_for(
                cast("Awaitable[Any]", client.ping()), timeout=timeout
            )
            # Get some basic stats
            info = await cast("Awaitable[dict[str, Any]]", client.info())
            duration_ms = (time.monotonic() - start_time) * 1000
            return HealthCheckResult(
                component="state_store",
                status=HealthStatus.HEALTHY,
                message="Redis state store is healthy",
                details={
                    "driver": "redis",
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory_human", "unknown"),
                    "url": self.url,
                },
                duration_ms=duration_ms,
                checked_at=datetime.now(UTC),
            )
        except Exception as exc:  # noqa: BLE001 — a health-check failure degrades the status, never raises
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.exception("Redis health check failed")
            return HealthCheckResult(
                component="state_store",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis state store unhealthy: {exc!s}",
                error=str(exc),
                details={
                    "driver": "redis",
                    "url": self.url,
                },
                duration_ms=duration_ms,
                checked_at=datetime.now(UTC),
            )
