"""Database monitoring classes"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime
from typing import Any

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import DatabaseConnectionError, DatabaseError
from quadkit.sql.monitoring.metrics import (
    ConnectionMetrics,
    DbMetricsCollector,
)

logger = get_logger(__name__)


class ConnectionPoolMonitor:
    """Monitors database connection pool usage"""

    def __init__(
        self,
        collector: DbMetricsCollector,
    ):
        self.collector = collector
        self.monitoring_task: asyncio.Task[Any] | None = None
        self.pool: Any = None
        self._provider: Any = None
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def _get_datetime(self) -> datetime:
        """Get current datetime."""
        return ambient_clock.now()

    async def start_monitoring(self, pool: Any, provider: Any = None) -> None:
        """Start monitoring a connection pool.

        Args:
            pool: The connection pool to monitor.
            provider: Optional database provider used for active connection
                probing. When supplied, :meth:`_probe_pool` will open a
                scoped connection and execute ``SELECT 1`` to verify the
                pool is healthy.
        """
        self.pool = pool
        self._provider = provider
        self.monitoring_task = create_tracked_task(
            self._monitor_pool(),
            self._background_tasks,
            name=f"sql_monitor_{id(self)}",
        )

    async def stop_monitoring(self) -> None:
        """Stop pool monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            # Await the cancelled task but suppress CancelledError for graceful shutdown
            with suppress(asyncio.CancelledError):
                await self.monitoring_task
            self.monitoring_task = None

    async def _monitor_pool(self) -> None:
        """Background task to monitor pool statistics"""
        while True:
            try:
                await self._collect_pool_metrics()
                await self._probe_pool()
                await asyncio.sleep(30)  # Collect metrics every 30 seconds
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
                logger.exception("Error monitoring connection pool")
                await asyncio.sleep(30)

    async def _probe_pool(self) -> None:
        """Actively probe the pool by running ``SELECT 1`` via a scoped connection.

        Opens a scoped connection from ``self._provider`` and executes a
        trivial ``SELECT 1`` query to confirm the pool is healthy. On any
        failure the error is logged at WARNING level and
        ``self._provider.evict_dead_connections()`` is called to remove
        dead connections and refill the pool. The count of remaining valid
        connections is logged at INFO level.

        This method never raises — monitoring must always remain resilient.
        """
        if self._provider is None:
            return
        try:
            async with self._provider.scoped_context():
                conn = await self._provider.get_scoped_connection()
                await conn.execute("SELECT 1")
        except Exception as exc:  # noqa: BLE001 — pool probe must never raise (driver errors are not builtin types); evict and keep monitoring
            logger.warning(
                "Pool probe failed — attempting to evict dead connections: %s",
                exc,
            )
            try:
                remaining = await self._provider.evict_dead_connections()
                logger.info(
                    "Evicted dead connections; %d valid connections remaining",
                    remaining,
                )
            except Exception:  # noqa: BLE001 — dead-connection eviction is best-effort; driver errors must not break monitoring
                pass

    async def _collect_pool_metrics(self) -> None:
        """Collect current pool metrics"""
        if not self.pool:
            return

        try:
            # Get pool statistics - these are typical attributes for SQLAlchemy pools
            active = getattr(self.pool, "_active_connections", 0)
            total = getattr(self.pool, "_total_connections", 0)

            # Ensure we have numeric values before proceeding
            # (especially important for tests using MagicMocks)
            try:
                active = int(active)
                total = int(total)
            except (TypeError, ValueError):
                active = 0
                total = 0

            available = total - active
            checked_out = active
            checked_in = available

            # Calculate utilization
            utilization = active / total if total > 0 else 0.0

            # Record metrics
            metrics = ConnectionMetrics(
                active_connections=active,
                total_connections=total,
                available_connections=available,
                checked_out_connections=checked_out,
                checked_in_connections=checked_in,
                utilization=utilization,
                timestamp=self._get_datetime(),
            )

            await self.collector.record_connection_metrics(metrics)

        except (
            DatabaseError,
            DatabaseConnectionError,
            OSError,
            ConnectionError,
            RuntimeError,
            TimeoutError,
        ):
            logger.exception("Error collecting pool metrics")

    async def get_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Get connection pool monitoring statistics"""
        return await self.collector.get_connection_stats(time_range_seconds)
