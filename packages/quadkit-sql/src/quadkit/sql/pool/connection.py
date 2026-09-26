"""
Connection pool implementations for community edition

Provides basic connection pooling functionality.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections import deque
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from quadkit.contracts import ConnectionPoolProtocol, DatabaseProviderProtocol
from quadkit.contracts.core import HealthCheckCategory, HealthCheckResult, HealthStatus
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import ConnectionPoolError

logger = get_logger(__name__)


class AbstractConnectionPool(ConnectionPoolProtocol, ABC):
    """
    Base connection pool with common functionality
    """

    # Poll interval used while waiting for an available connection. Tests may
    # monkeypatch this to a small value to speed up tests.
    DEFAULT_POLL_INTERVAL: float = 0.1

    def __init__(
        self,
        min_connections: int = 1,
        max_connections: int = 10,
        connection_timeout: float = 30.0,
        max_idle_time: float = 300.0,
        poll_interval: float | None = None,
        **kwargs: Any,
    ):
        self.min_connections = min_connections
        self._max_connections = max_connections
        self._connection_timeout = connection_timeout
        self.max_idle_time = max_idle_time

        # Effective poll interval used when waiting for a connection
        self._poll_interval = (
            poll_interval if poll_interval is not None else self.DEFAULT_POLL_INTERVAL
        )

        self._pool: deque[Any] = deque()
        self._active_connections = 0
        self._total_connections = 0
        self._initialized = False
        self._shutdown = False

        if hasattr(logger, "bind"):
            self.logger = logger.bind(pool=self.__class__.__name__)
        elif hasattr(logger, "getChild"):
            self.logger = logger.getChild(self.__class__.__name__)
        else:
            self.logger = logger

        # Statistics
        self._created_connections = 0
        self._destroyed_connections = 0
        self._acquired_connections = 0
        self._released_connections = 0
        self._start_time = ambient_clock.monotonic()

    @property
    def max_connections(self) -> int:
        """Get maximum number of connections."""
        return self._max_connections

    @property
    def connection_timeout(self) -> float:
        """Get connection timeout."""
        return self._connection_timeout

    async def initialize(self) -> None:
        """Initialize the connection pool"""
        if self._initialized:
            return

        # Create minimum connections
        for _ in range(self.min_connections):
            conn = await self._create_connection()
            self._pool.append((conn, ambient_clock.monotonic()))
            self._total_connections += 1
            self._created_connections += 1

        self._initialized = True
        self.logger.info(
            "Connection pool initialized with %s connections",
            self.min_connections,
        )

    async def shutdown(self) -> None:
        """Shutdown the connection pool"""
        if self._shutdown:
            return

        self._shutdown = True

        # Close all connections
        while self._pool:
            conn, _ = self._pool.popleft()
            await self._close_connection(conn)
            self._destroyed_connections += 1

        self._total_connections = 0
        self._active_connections = 0
        self.logger.info("Connection pool shutdown")

    @abstractmethod
    async def _create_connection(self) -> Any:
        """Create a new connection (implementation-specific)"""

    @abstractmethod
    async def _close_connection(self, connection: Any) -> None:
        """Close a connection (implementation-specific)"""

    @abstractmethod
    async def _validate_connection(self, connection: Any) -> bool:
        """Validate if a connection is still usable (implementation-specific)"""

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Any, None]:
        """Get a connection from the pool"""
        connection = await self._get_connection()
        try:
            yield connection
        finally:
            await self.return_connection(connection)

    async def _get_connection(self) -> Any:
        """Internal helper to get a connection without context manager (for testing)."""
        if self._shutdown:
            raise RuntimeError("Connection pool is shutdown")

        if not self._initialized:
            await self.initialize()

        connection = None
        connection_time = None

        # Try to get an existing connection
        if self._pool:
            connection, connection_time = self._pool.popleft()
            # Check if connection is still valid and not too old
            if not await self._validate_connection(connection):
                await self._close_connection(connection)
                self._destroyed_connections += 1
                self._total_connections -= 1
                connection = None
            elif (ambient_clock.monotonic()) - connection_time > self.max_idle_time:
                # Connection too old, close it
                await self._close_connection(connection)
                self._destroyed_connections += 1
                self._total_connections -= 1
                connection = None

        # Create new connection if needed
        if connection is None:
            if self._total_connections >= self.max_connections:
                # Wait for a connection to become available
                timeout = self.connection_timeout
                start_wait = ambient_clock.monotonic()
                while (
                    not self._pool
                    and ((ambient_clock.monotonic()) - start_wait) < timeout
                ):
                    await asyncio.sleep(self._poll_interval)

                if self._pool:
                    connection, connection_time = self._pool.popleft()
                else:
                    raise ConnectionPoolError(
                        f"Connection pool exhausted. Could not acquire connection in {timeout}s. "
                        f"Pool size: {self.max_connections}, active: {self._active_connections}",
                    )
            else:
                connection = await self._create_connection()
                connection_time = ambient_clock.monotonic()
                self._total_connections += 1
                self._created_connections += 1

        self._active_connections += 1
        self._acquired_connections += 1
        return connection

    async def return_connection(self, connection: Any) -> None:
        """Return a connection to the pool.

        This method is generally called automatically by get_connection().
        Manual call is supported for specialized testing or legacy code.
        """
        if not connection:
            return

        self._active_connections -= 1
        self._released_connections += 1

        # Return connection to pool if still valid
        if await self._validate_connection(connection):
            self._pool.append((connection, ambient_clock.monotonic()))
        else:
            await self._close_connection(connection)
            self._destroyed_connections += 1
            self._total_connections -= 1

    async def get_pool_stats(self) -> dict[str, Any]:
        """Get pool statistics"""
        uptime = (ambient_clock.monotonic()) - self._start_time

        return {
            "pool_size": len(self._pool),
            "active_connections": self._active_connections,
            "total_connections": self._total_connections,
            "max_connections": self.max_connections,
            "min_connections": self.min_connections,
            "created_connections": self._created_connections,
            "destroyed_connections": self._destroyed_connections,
            "acquired_connections": self._acquired_connections,
            "released_connections": self._released_connections,
            "uptime_seconds": uptime,
            "utilization_rate": (
                self._active_connections / self.max_connections
                if self.max_connections > 0
                else 0
            ),
            "idle_connections": len(self._pool),
        }

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check pool health"""
        try:
            stats = await self.get_pool_stats()

            # Basic health checks
            issues = []

            if stats["active_connections"] >= stats["max_connections"] * 0.9:
                issues.append("High connection utilization")

            if stats["pool_size"] < stats["min_connections"]:
                issues.append("Below minimum connection count")

            utilization = stats["utilization_rate"]
            if utilization > 0.95:
                status = HealthStatus.UNHEALTHY
                error = "Critical connection pool utilization"
            elif utilization > 0.85:
                status = HealthStatus.UNHEALTHY
                error = "High connection pool utilization"
            else:
                status = HealthStatus.HEALTHY
                error = None

            return HealthCheckResult(
                component=self.__class__.__name__,
                status=status,
                details={
                    "message": f"Pool utilization: {utilization:.1%}",
                    "issues": issues,
                    "stats": stats,
                },
                error=error,
                checked_at=ambient_clock.now(),
                category=HealthCheckCategory.READINESS,
            )

        except (OSError, ConnectionError, RuntimeError, TimeoutError) as e:
            return HealthCheckResult(
                component=self.__class__.__name__,
                status=HealthStatus.UNHEALTHY,
                details={
                    "issues": ["Unable to get pool statistics"],
                    "stats": {},
                },
                error=f"Health check failed: {e!s}",
                checked_at=ambient_clock.now(),
                category=HealthCheckCategory.READINESS,
            )


class _ProviderConnection:
    """Lightweight proxy for provider objects used as "connections" in SimpleConnectionPool.

    This keeps backwards-compatible behavior (the provider is accessible via
    the `_provider` attribute and most attribute lookups are delegated to the
    underlying provider) while allowing the pool to manage connection-like
    objects in one place.
    """

    __slots__ = ("_provider",)

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<ProviderConnection provider={self._provider!r}>"

    @property
    def provider(self) -> Any:  # pragma: no cover - convenience property
        return self._provider

    @property
    def _is_provider_proxy(
        self,
    ) -> bool:  # pragma: no cover - used for testing/inspection
        return True

    @asynccontextmanager
    async def as_context(self) -> AsyncGenerator[_ProviderConnection, None]:
        """Return a simple context manager that yields the proxy (compat shim)."""
        yield self

    @staticmethod
    def unwrap(conn: Any) -> Any:  # pragma: no cover - utility
        return getattr(conn, "_provider", conn)

    @asynccontextmanager
    async def dummy(self) -> AsyncGenerator[_ProviderConnection, None]:
        yield self


class SimpleConnectionPool(AbstractConnectionPool):
    """
    Simple connection pool that creates connections on demand

    This is a basic implementation that doesn't use any external pooling libraries.

    Parameters:
        provider: The database provider object used to satisfy connections.
        use_provider_proxy: If True, returns a lightweight proxy object instead
            of the raw provider when creating connections. Defaults to False
            to preserve backwards compatibility.
    """

    def __init__(
        self,
        provider: DatabaseProviderProtocol,
        use_provider_proxy: bool = False,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.provider = provider
        self.use_provider_proxy = use_provider_proxy

    async def _create_connection(self) -> Any:
        """Create a new connection using the provider

        Depending on the `use_provider_proxy` flag this returns either the
        provider itself (default) or a `_ProviderConnection` proxy that
        delegates attribute access to the underlying provider.
        """
        if self.use_provider_proxy:
            return _ProviderConnection(self.provider)
        # For simple pooling, return the provider itself as the "connection"
        return self.provider

    async def _close_connection(self, connection: Any) -> None:
        """Close a connection"""
        # For simple pooling with providers, we don't actually close the provider
        # The provider manages its own connection lifecycle

    async def _validate_connection(self, connection: Any) -> bool:
        """Validate if a connection is still usable via a lightweight ping.

        First checks the provider's in-memory connected flag; if connected,
        executes ``SELECT 1`` to verify the underlying TCP connection is still
        alive.  Stale connections (e.g. closed by the server after idle
        timeout) are detected and discarded before being handed to a caller.
        """
        # Fast path: if the provider exposes is_connected(), trust it as the
        # first gate.
        if hasattr(connection, "is_connected"):
            try:
                res = await connection.is_connected()
                if not res:
                    return False
            except Exception:  # noqa: BLE001 — any probe failure means the connection cannot be confirmed alive; discard it
                return False

        # Slow path: issue a lightweight round-trip to confirm the physical
        # connection is alive.
        if hasattr(connection, "execute"):
            try:
                await connection.execute("SELECT 1")
            except Exception:  # noqa: BLE001 — driver/framework errors (e.g. asyncpg ConnectionClosedError) on a stale connection must discard, not propagate
                logger.warning(
                    "db.pool.connection_stale",
                    message="Pool connection failed SELECT 1 ping; discarding.",
                )
                return False

        return True

    async def warm(self, count: int | None = None) -> None:
        """Pre-create connections to avoid cold-start latency.

        Args:
            count: Number of connections to open. Defaults to ``min_connections``
                   if not specified. Will not exceed ``max_connections``.
        """
        target = min(
            count if count is not None else self.min_connections,
            self.max_connections,
        )
        while self._total_connections < target:
            conn = await self._create_connection()
            self._pool.append((conn, ambient_clock.monotonic()))
            self._total_connections += 1
            self._created_connections += 1

    async def validate_connections(self) -> int:
        """Validate all idle connections in the pool, evicting dead ones.

        Iterates through all idle connections, discards those that are expired
        (older than ``max_idle_time``) or fail validation, then refills the
        pool to ``min_connections`` via ``warm()``.

        Returns:
            Number of valid connections remaining after validation.
        """
        retained: deque[tuple[Any, float]] = deque()
        while self._pool:
            connection, created_at = self._pool.popleft()
            # Check if connection is expired
            expired = (ambient_clock.monotonic()) - created_at > self.max_idle_time
            # Validate connection if not expired
            valid = False if expired else await self._validate_connection(connection)
            if valid:
                retained.append((connection, created_at))
                continue
            # Close invalid or expired connection
            await self._close_connection(connection)
            self._destroyed_connections += 1
            self._total_connections -= 1

        self._pool = retained
        # Refill pool to minimum connections
        await self.warm()
        return len(self._pool)


__all__ = ["AbstractConnectionPool", "SimpleConnectionPool"]
