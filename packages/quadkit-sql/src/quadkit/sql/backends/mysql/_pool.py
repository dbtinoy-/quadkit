"""MySQL database driver implementation"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.data import ConnectionPoolProtocol
from quadkit.contracts.infra.resilience import CircuitBreakerProtocol, RetryConfig
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.backends.mysql._shims import (
    HAS_MYSQL,
    MySQLError,
    aiomysql,
)
from quadkit.sql.lib.retry import retry_call
from quadkit.sql.monitoring import DatabaseMonitor

logger = get_logger(__name__)

HAS_MONITORING = True

from quadkit.sql.backends.mysql._connection import MySQLConnection
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)


class MySQLConnectionPool(ConnectionPoolProtocol):
    """MySQL connection pool with health checks and resilience"""

    def __init__(
        self,
        host: str,
        port: int = 3306,
        user: str = "",
        password: str = "",
        database: str = "",
        min_size: int = 10,
        max_size: int = 20,
        ssl: dict[str, Any] | None = None,
        retry_config: RetryConfig | None = None,
        circuit_breaker: CircuitBreakerProtocol | None = None,
        monitor: DatabaseMonitor | None = None,
        **kwargs: Any,
    ) -> None:
        if not HAS_MYSQL:
            raise ImportError(
                "aiomysql is required for MySQL support. Install with: pip install quadkit-sql[mysql]",
            )

        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.min_size = min_size
        self.max_size = max_size
        self.ssl = ssl
        self.pool_kwargs = kwargs
        self._pool: Any | None = None
        self._is_healthy = False
        self._last_health_check = 0.0
        self._connection_count = 0
        self._error_count = 0
        self._total_connections_created = 0
        self._background_tasks: set[asyncio.Task[Any]] = set()

        # Resilience patterns.
        #
        # ``DatabaseConnectionError`` must be in ``retry_on``: ``_create_pool``
        # wraps every driver failure in ``DatabaseConnectionError`` before
        # the exception reaches ``retry_call``, so a config that only lists
        # driver-level types (``MySQLError``) would never match and the
        # retry policy would be silently dead (BUG #38).
        self.retry_config = retry_config or RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            retry_on=(MySQLError, ConnectionError, DatabaseConnectionError),
        )
        self.circuit_breaker: CircuitBreakerProtocol | None = circuit_breaker

        # Monitoring
        self.monitor = monitor
        if self.monitor and HAS_MONITORING:
            # Start pool monitoring via TaskManager for graceful shutdown

            self._monitoring_task = create_tracked_task(
                self.monitor.start_pool_monitoring(self),
                self._background_tasks,
                name=f"mysql_pool_monitor_{id(self)}",
            )

    @property
    def max_connections(self) -> int:
        return self.max_size

    @property
    def connection_timeout(self) -> float:
        return cast("float", self.pool_kwargs.get("timeout", 10.0))

    async def initialize(self) -> None:
        """Initialize the connection pool with SSL and retry logic"""
        if self._pool:
            return

        # Configure SSL if specified
        pool_kwargs = self.pool_kwargs.copy()
        if self.ssl:
            pool_kwargs.update(self.ssl)

        # Set pool size parameters
        pool_kwargs.update(
            {
                "minsize": self.min_size,
                "maxsize": self.max_size,
            },
        )

        # Create connection pool
        if self.retry_config:
            await retry_call(
                self._create_pool,
                config=self.retry_config,
                pool_kwargs=pool_kwargs,
            )
        else:
            await self._create_pool(pool_kwargs)

    async def _create_pool(self, pool_kwargs: dict[str, Any]) -> None:
        """Internal pool creation with error handling"""
        try:
            self._pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                **pool_kwargs,
            )
            self._total_connections_created += 1
            self._is_healthy = True
            logger.info(
                "MySQL pool initialized with %s-%s connections",
                self.min_size,
                self.max_size,
            )
        except Exception as e:  # noqa: BLE001 — pool initialization must catch all infrastructure errors
            self._error_count += 1
            self._is_healthy = False
            logger.exception("Failed to create MySQL pool")
            raise DatabaseConnectionError(f"Pool creation failed: {e}") from e

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[MySQLConnection, None]:
        """Get a connection from the pool with circuit breaker protection"""
        if not self._pool:
            await self.initialize()

        if self._pool is None:
            raise RuntimeError("MySQL pool not initialized")

        # Use circuit breaker for connection acquisition
        logger.debug("Acquiring MySQL connection")
        if self.circuit_breaker:
            async with self.circuit_breaker.protect():
                try:
                    async with self._pool.acquire() as conn:
                        self._connection_count += 1
                        yield MySQLConnection(conn, self.monitor)
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

        else:
            try:
                async with self._pool.acquire() as conn:
                    self._connection_count += 1
                    yield MySQLConnection(conn, self.monitor)
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
                    f"Connection acquisition failed: {e}"
                ) from e

    async def shutdown(self) -> None:
        """Close all connections in the pool"""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._is_healthy = False

            # Stop monitoring
            if self.monitor and HAS_MONITORING:
                await self.monitor.stop_pool_monitoring()

            logger.info("MySQL pool closed")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check on the MySQL connection pool"""
        current_time = ambient_clock.timestamp()

        # Cache health checks for 30 seconds
        if current_time - self._last_health_check < 30.0 and self._is_healthy:
            return HealthCheckResult(
                component="database",
                status=HealthStatus.HEALTHY,
                details={
                    "host": f"{self.host}:{self.port}",
                    "database": self.database,
                    "pool_size": f"{self.min_size}-{self.max_size}",
                    "connections_created": self._total_connections_created,
                    "cached": True,
                },
                checked_at=datetime.fromtimestamp(current_time, UTC),
            )

        self._last_health_check = current_time

        if not self._pool:
            self._is_healthy = False
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message="Pool not initialized",
                error="Pool not initialized",
                details={
                    "host": f"{self.host}:{self.port}",
                    "database": self.database,
                    "pool_size": f"{self.min_size}-{self.max_size}",
                },
                checked_at=datetime.fromtimestamp(current_time, UTC),
            )

        try:
            # Test connection with a simple query
            async with self.get_connection() as conn:  # type: MySQLConnection
                result = await conn.execute("SELECT 1 as health_check")
                if result is not None:
                    self._is_healthy = True
                    return HealthCheckResult(
                        component="database",
                        status=HealthStatus.HEALTHY,
                        details={
                            "host": f"{self.host}:{self.port}",
                            "database": self.database,
                            "pool_size": f"{self.min_size}-{self.max_size}",
                            "connections_created": self._total_connections_created,
                            "active_connections": self._connection_count,
                            "error_count": self._error_count,
                            "circuit_breaker_state": (
                                str(self.circuit_breaker.state)
                                if self.circuit_breaker
                                else "unknown"
                            ),
                        },
                        checked_at=datetime.fromtimestamp(current_time, UTC),
                    )
                self._is_healthy = False
                return HealthCheckResult(
                    component="database",
                    status=HealthStatus.UNHEALTHY,
                    message="Health check query failed",
                    error="Health check query failed",
                    details={
                        "host": f"{self.host}:{self.port}",
                        "database": self.database,
                        "pool_size": f"{self.min_size}-{self.max_size}",
                    },
                    checked_at=datetime.fromtimestamp(current_time, UTC),
                )
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
            Exception,
        ) as e:
            self._is_healthy = False
            if not isinstance(e, DatabaseConnectionError):
                self._error_count += 1
            logger.exception("MySQL health check failed")
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                error=str(e),
                details={
                    "host": f"{self.host}:{self.port}",
                    "database": self.database,
                    "pool_size": f"{self.min_size}-{self.max_size}",
                    "error_count": self._error_count,
                },
                checked_at=datetime.fromtimestamp(current_time, UTC),
            )

    async def get_pool_stats(self) -> dict[str, Any]:
        """Get MySQL connection pool statistics"""
        return {
            "host": f"{self.host}:{self.port}",
            "database": self.database,
            "pool_size": f"{self.min_size}-{self.max_size}",
            "is_initialized": self._pool is not None,
            "is_healthy": self._is_healthy,
            "total_connections_created": self._total_connections_created,
            "active_connection_count": self._connection_count,
            "error_count": self._error_count,
            "circuit_breaker_state": (
                str(self.circuit_breaker.state) if self.circuit_breaker else "unknown"
            ),
            "last_health_check": self._last_health_check,
            "monitoring_enabled": self.monitor is not None,
        }

    async def get_query_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Get query stats"""
        return {}


def create_mysql_pool(
    host: str = "localhost",
    port: int = 3306,
    user: str = "root",
    password: str = "",
    database: str = "",
    min_size: int = 10,
    max_size: int = 20,
    ssl: dict[str, Any] | None = None,
    retry_config: RetryConfig | None = None,
    circuit_breaker: CircuitBreakerProtocol | None = None,
    monitor: DatabaseMonitor | None = None,
    **kwargs: Any,
) -> MySQLConnectionPool:
    """Factory function to create MySQL connection pool with resilience features

    Args:
        host: MySQL server host
        port: MySQL server port
        user: MySQL username
        password: MySQL password
        database: MySQL database name
        min_size: Minimum pool size
        max_size: Maximum pool size
        ssl: SSL configuration dictionary
        retry_config: Retry configuration for connection operations
        circuit_breaker: Pre-configured circuit breaker instance for protection
        monitor: Database monitor for observability
        **kwargs: Additional aiomysql pool arguments

    Returns:
        Configured MySQL connection pool
    """
    return MySQLConnectionPool(  # type: ignore[abstract]
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        min_size=min_size,
        max_size=max_size,
        ssl=ssl,
        retry_config=retry_config,
        circuit_breaker=circuit_breaker,
        monitor=monitor,
        **kwargs,
    )
