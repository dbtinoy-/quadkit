"""SQLite database driver implementation"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.contracts.data import ConnectionPoolProtocol
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

logger = get_logger(__name__)

# Declare optional third-party/runtime names as Any so we can provide runtime fallbacks
from quadkit.contracts import (
    HealthCheckResult,
    HealthStatus,
    RetryConfig,
)
from quadkit.contracts.infra.resilience import CircuitBreakerProtocol
from quadkit.sql.backends.sqlite._connection import HAS_MONITORING, SQLiteConnection
from quadkit.sql.backends.sqlite._shims import (  # noqa: F401
    HAS_MONITORING,
    HAS_SQLITE,
    DatabaseMonitor,
    aiosqlite,
)
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
)
from quadkit.sql.lib.retry import retry_call


class SQLiteConnectionPool(ConnectionPoolProtocol):
    """SQLite connection pool (single connection for simplicity)"""

    def __init__(
        self,
        database: str = ":memory:",
        retry_config: RetryConfig | None = None,
        circuit_breaker: CircuitBreakerProtocol | None = None,
        monitor: DatabaseMonitor | None = None,
        **kwargs: Any,
    ) -> None:
        if not HAS_SQLITE:
            raise ImportError(
                "aiosqlite is required for SQLite support. Install with: pip install quadkit-sql[sqlite]",
            )

        self.database = database
        self.pool_kwargs = kwargs
        self._conn: aiosqlite.Connection | None = None
        self._file_identity: tuple[int, int] | None = None
        self._is_healthy = False
        self._last_health_check = 0.0
        self._connection_count = 0
        self._error_count = 0
        self._total_connections_created = 0
        self._monitoring_task: asyncio.Task[None] | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()

        # Resilience patterns
        self.retry_config = retry_config or RetryConfig(
            max_attempts=3,
            base_delay=1.0,
        )
        self.circuit_breaker: CircuitBreakerProtocol | None = circuit_breaker

        # Monitoring
        self.monitor = monitor
        if self.monitor and HAS_MONITORING:
            # Start pool monitoring via TaskManager for graceful shutdown

            self._monitoring_task = create_tracked_task(
                self.monitor.start_pool_monitoring(self),
                self._background_tasks,
                name=f"sqlite_pool_monitor_{id(self)}",
            )

    @property
    def max_connections(self) -> int:
        return 1

    @property
    def connection_timeout(self) -> float:
        return cast("float", self.pool_kwargs.get("timeout", 5.0))

    async def initialize(self) -> None:
        """Initialize the connection with retry logic"""
        if self._conn:
            return

        # Create connection with retry logic
        if self.retry_config:
            await retry_call(self._create_connection, config=self.retry_config)
        else:
            await self._create_connection()

    async def _create_connection(self) -> None:
        """Internal connection creation with error handling"""
        try:
            self._conn = await aiosqlite.connect(self.database, **self.pool_kwargs)
            self._file_identity = self._stat_identity()
            self._total_connections_created += 1
            self._is_healthy = True
            logger.info("SQLite connection initialized for %s", self.database)
        except Exception as e:  # noqa: BLE001 — connection creation must catch all infrastructure errors
            self._error_count += 1
            self._is_healthy = False
            logger.exception("Failed to create SQLite connection")
            raise DatabaseConnectionError(f"Connection creation failed: {e}") from e

    def _stat_identity(self) -> tuple[int, int] | None:
        """Return (st_dev, st_ino) of the database file, or None if missing/empty."""
        if self.database == ":memory:":
            return None
        try:
            st = Path(self.database).stat()
        except OSError:
            return None
        return (st.st_dev, st.st_ino)

    def _file_state_ok(self) -> bool:
        """True if the on-disk database file still matches the connected file.

        Detects the deleted-inode case where the database file was unlinked
        (or replaced) while the connection stays open against the old inode,
        which would silently serve stale data.
        """
        if self.database == ":memory:":
            return True
        if self._file_identity is None:
            # No connection established yet; the file may legitimately not
            # exist yet (SQLite creates it lazily on first connect).
            return True
        current = self._stat_identity()
        if current is None:
            return False
        return current == self._file_identity

    async def _invalidate_stale_connection(self) -> None:
        """Close and drop a connection whose database file no longer matches."""
        if self._conn:
            try:
                await self._conn.close()
            except Exception:  # noqa: BLE001, S110 — best-effort close of a stale handle
                pass
            self._conn = None
        self._file_identity = None
        self._is_healthy = False
        self._error_count += 1
        logger.error(
            "sqlite.db_file_stale",
            message="SQLite database file missing or replaced; stale connection closed",
            database=self.database,
        )

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[SQLiteConnection, None]:
        """Get the initialized connection with circuit breaker protection"""
        if not self._conn:
            await self.initialize()

        if self._conn is None:
            raise RuntimeError("SQLite connection not initialized")

        if not self._file_state_ok():
            await self._invalidate_stale_connection()
            raise DatabaseConnectionError(
                f"SQLite database file {self.database} is missing or was replaced "
                "(stale connection refused); restart the application to re-create it",
            )

        # Use circuit breaker if configured
        if self.circuit_breaker:
            try:
                async with self.circuit_breaker.protect():
                    self._connection_count += 1
                    yield SQLiteConnection(self._conn, self.monitor)
            except (
                OSError,
                ConnectionError,
                RuntimeError,
                TimeoutError,
                Exception,
            ) as e:
                self._error_count += 1
                self._is_healthy = False
                logger.exception("Connection acquisition failed (breaker)")
                if isinstance(e, DatabaseConnectionError):
                    raise
                raise DatabaseConnectionError(
                    f"Connection acquisition failed: {e}",
                ) from e

        else:
            try:
                self._connection_count += 1
                yield SQLiteConnection(self._conn, self.monitor)
            except (
                OSError,
                ConnectionError,
                RuntimeError,
                TimeoutError,
                Exception,
            ) as e:
                self._error_count += 1
                self._is_healthy = False
                logger.exception("Connection acquisition failed")
                raise DatabaseConnectionError(
                    f"Connection acquisition failed: {e}",
                ) from e

    async def shutdown(self) -> None:
        """Close the connection"""
        if self._conn:
            await self._conn.close()
            self._conn = None
            self._is_healthy = False

            # Stop monitoring
            if self.monitor and HAS_MONITORING:
                await self.monitor.stop_pool_monitoring()

            logger.info("SQLite connection closed")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check on the SQLite connection and return a standard result."""
        current_time = ambient_clock.timestamp()

        if not self._file_state_ok():
            await self._invalidate_stale_connection()
            self._last_health_check = current_time
            details = {
                "database": self.database,
                "file_state": "missing_or_replaced",
                "error_count": self._error_count,
            }
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message=(
                    f"SQLite database file {self.database} is missing or was "
                    "replaced; stale connection closed"
                ),
                details=details,
                checked_at=datetime.fromtimestamp(current_time, UTC),
            )

        # Cache health checks for 30 seconds
        if current_time - self._last_health_check < 30.0 and self._is_healthy:
            details = {
                "database": self.database,
                "connections_created": self._total_connections_created,
                "active_connections": self._connection_count,
                "error_count": self._error_count,
                "circuit_breaker_state": (
                    str(self.circuit_breaker.state)
                    if self.circuit_breaker
                    else "unknown"
                ),
                "cached": True,
            }
            return HealthCheckResult(
                component="database",
                status=HealthStatus.HEALTHY,
                details=details,
                checked_at=datetime.fromtimestamp(current_time, UTC),
            )

        self._last_health_check = current_time

        if not self._conn:
            self._is_healthy = False
            details = {"database": self.database}
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message="Connection not initialized",
                details=details,
                checked_at=datetime.fromtimestamp(current_time, UTC),
            )

        try:
            # Test connection with a simple query
            async with self.get_connection() as conn:  # type: SQLiteConnection
                result = await conn.execute("SELECT 1 as health_check")
                if result is not None:
                    self._is_healthy = True
                    details = {
                        "database": self.database,
                        "connections_created": self._total_connections_created,
                        "active_connections": self._connection_count,
                        "error_count": self._error_count,
                        "circuit_breaker_state": (
                            str(self.circuit_breaker.state)
                            if self.circuit_breaker
                            else "unknown"
                        ),
                    }
                    return HealthCheckResult(
                        component="database",
                        status=HealthStatus.HEALTHY,
                        details=details,
                        checked_at=datetime.fromtimestamp(current_time, UTC),
                    )
                self._is_healthy = False
                details = {"database": self.database}
                return HealthCheckResult(
                    component="database",
                    status=HealthStatus.UNHEALTHY,
                    message="Health check query failed",
                    details=details,
                    checked_at=datetime.fromtimestamp(current_time, UTC),
                )
        except (
            DatabaseError,
            DatabaseConnectionError,
            OSError,
            ConnectionError,
            RuntimeError,
            TimeoutError,
            Exception,
        ) as e:
            self._is_healthy = False

            if not isinstance(e, DatabaseConnectionError):
                self._error_count += 1

            logger.exception("SQLite health check failed")
            details = {"database": self.database, "error_count": self._error_count}
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                details=details,
                checked_at=datetime.fromtimestamp(current_time, UTC),
            )

    async def get_pool_stats(self) -> dict[str, Any]:
        """Get SQLite connection statistics"""
        return {
            "database": self.database,
            "is_initialized": self._conn is not None,
            "is_healthy": self._is_healthy,
            "file_exists": (
                Path(self.database).exists() if self.database != ":memory:" else True
            ),
            "file_state_ok": self._file_state_ok(),
            "total_connections_created": self._total_connections_created,
            "active_connection_count": self._connection_count,
            "error_count": self._error_count,
            "circuit_breaker_state": getattr(self.circuit_breaker, "state", "unknown"),
            "last_health_check": self._last_health_check,
        }

    async def get_query_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Get query stats"""
        return {}


def create_sqlite_pool(
    database: str = ":memory:",
    retry_config: RetryConfig | None = None,
    circuit_breaker: CircuitBreakerProtocol | None = None,
    monitor: DatabaseMonitor | None = None,
    **kwargs: Any,
) -> SQLiteConnectionPool:
    """Factory function to create SQLite connection pool with resilience features

    Args:
        database: SQLite database file path or ":memory:" for in-memory database
        retry_config: Retry configuration for connection operations
        circuit_breaker: Pre-configured circuit breaker instance for protection
        monitor: Database monitor for observability
        **kwargs: Additional aiosqlite connection arguments

    Returns:
        Configured SQLite connection pool
    """
    return SQLiteConnectionPool(  # type: ignore[abstract]
        database=database,
        retry_config=retry_config,
        circuit_breaker=circuit_breaker,
        monitor=monitor,
        **kwargs,
    )
