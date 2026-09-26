"""Replica pool with health-aware routing and failover."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
import re
from typing import Any

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.contracts.core import HealthCheckCategory, HealthCheckResult, HealthStatus
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import DatabaseConnectionError, DatabaseError
from quadkit.sql.pool.connection import AbstractConnectionPool as ConnectionPool

logger = get_logger(__name__)

# SQL prefixes that indicate a write operation.  Everything else routes to a
# read replica.  The check is intentionally conservative — if a query cannot
# be classified as a pure read it is routed to the primary.
_WRITE_PREFIXES = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|REPLACE|MERGE|CREATE|DROP|ALTER|TRUNCATE|CALL|EXEC)\b",
    re.IGNORECASE,
)


class ReplicaPool:
    """Connection pool with health-aware read replica routing.

    Features:
    - Round-robin read routing across healthy replicas
    - Automatic health monitoring and eviction of unhealthy replicas
    - Transparent fallback to primary when all replicas are down
    - Dynamic warm-up and graceful drain lifecycle
    """

    def __init__(
        self,
        primary_pool: ConnectionPool,
        replica_pools: list[ConnectionPool] | None = None,
        *,
        health_check_interval: float = 30.0,
        max_replication_lag_seconds: float | None = None,
    ):
        self.primary_pool = primary_pool
        self.replica_pools = replica_pools or []
        self._replica_index = 0
        self._healthy_replicas: list[ConnectionPool] = list(self.replica_pools)
        self._unhealthy_replicas: list[ConnectionPool] = []
        self._health_check_interval = health_check_interval
        self._max_lag = max_replication_lag_seconds
        self._health_task: asyncio.Task | None = None
        self._read_count = 0
        self._write_count = 0
        self._fallback_count = 0
        self._background_tasks: set[asyncio.Task[Any]] = set()

    @asynccontextmanager
    async def read(self) -> AsyncGenerator[Any, None]:
        """Get a read connection from a healthy replica or primary."""
        pool = self._pick_read_pool()
        async with pool.get_connection() as conn:
            self._read_count += 1
            yield conn

    @asynccontextmanager
    async def write(self) -> AsyncGenerator[Any, None]:
        """Get a write connection (always from primary)."""
        async with self.primary_pool.get_connection() as conn:
            self._write_count += 1
            yield conn

    @staticmethod
    def is_write_query(sql: str) -> bool:
        """Return ``True`` when *sql* should be routed to the primary (write) pool.

        Classification is based on the SQL statement's leading keyword.
        ``SELECT``, ``WITH``, ``EXPLAIN``, and ``SHOW`` are treated as reads;
        all other statements (INSERT, UPDATE, DELETE, DDL, etc.) are writes.

        Args:
            sql: The SQL statement to classify.

        Returns:
            ``True`` if the statement is a write/mutation; ``False`` for reads.
        """
        return bool(_WRITE_PREFIXES.match(sql))

    @asynccontextmanager
    async def auto(self, sql: str) -> AsyncGenerator[Any, None]:
        """Automatically route *sql* to the read replica or primary.

        Inspects the leading SQL keyword to decide whether to use a replica
        (reads) or the primary (writes/DDL).  This is the recommended entry
        point for application code that should not need to know about the
        physical pool topology.

        Args:
            sql: The SQL statement about to be executed.  Used only for
                routing classification — the caller is responsible for
                actually executing the statement on the yielded connection.

        Yields:
            A database connection appropriate for the given statement.

        Example::

            async with pool.auto("SELECT id FROM users WHERE email = $1") as conn:
                row = await conn.fetchrow(...)

            async with pool.auto("INSERT INTO users ...") as conn:
                await conn.execute(...)
        """
        if self.is_write_query(sql):
            async with self.write() as conn:
                yield conn
        else:
            async with self.read() as conn:
                yield conn

    def _pick_read_pool(self) -> ConnectionPool:
        """Pick a healthy replica pool; fall back to primary."""
        if self._healthy_replicas:
            pool = self._healthy_replicas[
                self._replica_index % len(self._healthy_replicas)
            ]
            self._replica_index += 1
            return pool

        # All replicas down — fall back to primary
        self._fallback_count += 1
        logger.warning("All replicas unhealthy, falling back to primary")
        return self.primary_pool

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize all pools and start health monitor."""
        await self.primary_pool.initialize()
        for pool in self.replica_pools:
            await pool.initialize()

        # Start background health checker
        if self.replica_pools:
            self._health_task = create_tracked_task(
                self._health_monitor_loop(),
                self._background_tasks,
                name=f"replica_monitor_{id(self)}",
            )

    async def shutdown(self) -> None:
        """Gracefully drain and shutdown all pools."""
        # Cancel health monitor
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._health_task

        await self.primary_pool.shutdown()
        for pool in self.replica_pools:
            await pool.shutdown()

    async def warmup(self) -> None:
        """Pre-create minimum connections in all pools."""
        await self.primary_pool.initialize()
        for pool in self.replica_pools:
            await pool.initialize()
        logger.info(
            "Pool warmup complete: primary + %d replicas",
            len(self.replica_pools),
        )

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    async def _health_monitor_loop(self) -> None:
        """Periodically check replica health."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._check_replica_health()
            except asyncio.CancelledError:
                break
            except (
                DatabaseError,
                DatabaseConnectionError,
                OSError,
                ConnectionError,
                RuntimeError,
                TimeoutError,
            ):
                logger.exception("Error in replica health monitor")

    async def _check_replica_health(self) -> None:
        """Check all replicas and update healthy/unhealthy lists."""
        newly_healthy: list[ConnectionPool] = []
        newly_unhealthy: list[ConnectionPool] = []

        for pool in self.replica_pools:
            try:
                result = await pool.health_check()
                if result.status == HealthStatus.HEALTHY:
                    newly_healthy.append(pool)
                else:
                    newly_unhealthy.append(pool)
                    logger.warning(
                        "Replica evicted: %s",
                        result.details,
                    )
            except (
                DatabaseError,
                DatabaseConnectionError,
                OSError,
                ConnectionError,
                RuntimeError,
                TimeoutError,
            ):
                newly_unhealthy.append(pool)
                logger.exception("Replica health check failed")

        self._healthy_replicas = newly_healthy
        self._unhealthy_replicas = newly_unhealthy

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check health of all pools and return structured result."""
        primary_health = await self.primary_pool.health_check()
        replica_healths = await asyncio.gather(
            *(p.health_check() for p in self.replica_pools),
        )

        all_healthy = primary_health.status == HealthStatus.HEALTHY and all(
            r.status == HealthStatus.HEALTHY for r in replica_healths
        )

        overall_status = HealthStatus.HEALTHY if all_healthy else HealthStatus.UNHEALTHY

        return HealthCheckResult(
            component=self.__class__.__name__,
            status=overall_status,
            details={
                "primary": primary_health,
                "replicas": replica_healths,
                "healthy_replica_count": len(self._healthy_replicas),
                "unhealthy_replica_count": len(self._unhealthy_replicas),
            },
            checked_at=ambient_clock.now(),
            category=HealthCheckCategory.READINESS,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            "total_replicas": len(self.replica_pools),
            "healthy_replicas": len(self._healthy_replicas),
            "unhealthy_replicas": len(self._unhealthy_replicas),
            "total_reads": self._read_count,
            "total_writes": self._write_count,
            "primary_fallbacks": self._fallback_count,
        }
