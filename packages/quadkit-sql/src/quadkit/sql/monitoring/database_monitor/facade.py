"""DatabaseMonitor facade coordinating query, transaction, pool, and health monitors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.monitoring.database_monitor.health import DatabaseHealthChecker
from quadkit.sql.monitoring.database_monitor.pool import ConnectionPoolMonitor
from quadkit.sql.monitoring.database_monitor.query import QueryMonitor
from quadkit.sql.monitoring.database_monitor.transaction import TransactionMonitor
from quadkit.sql.monitoring.metrics import DbMetricsCollector

logger = get_logger(__name__)


class DatabaseMonitor:
    """Comprehensive database monitoring"""

    def __init__(
        self,
        collector: DbMetricsCollector | None = None,
        slow_query_threshold: float = 1.0,
    ):
        from quadkit.sql.monitoring.metrics import (
            InMemoryDbMetricsCollector,
        )

        self.collector = collector or InMemoryDbMetricsCollector()
        self.query_monitor = QueryMonitor(self.collector, slow_query_threshold)
        self.pool_monitor = ConnectionPoolMonitor(self.collector)
        self.transaction_monitor = TransactionMonitor(self.collector)
        self.health_checker = DatabaseHealthChecker(self.collector)

    def _get_datetime(self) -> datetime:
        """Get current datetime."""
        return ambient_clock.now()

    async def start_pool_monitoring(
        self,
        pool: Any,
        provider: Any | None = None,
    ) -> None:
        """Start monitoring a connection pool.

        Args:
            pool: The pool or provider object to monitor.
            provider: Optional provider used for active ``SELECT 1`` probing.
                When omitted, the pool itself is used as the provider only if
                it exposes ``scoped_context()``.
        """
        probe_provider = provider
        if probe_provider is None and hasattr(pool, "scoped_context"):
            probe_provider = pool
        await self.pool_monitor.start_monitoring(pool, probe_provider)

    async def stop_pool_monitoring(self) -> None:
        """Stop pool monitoring"""
        await self.pool_monitor.stop_monitoring()

    def get_query_monitor(self) -> QueryMonitor:
        """Get the query monitor"""
        return self.query_monitor

    def get_transaction_monitor(self) -> TransactionMonitor:
        """Get the transaction monitor"""
        return self.transaction_monitor

    def get_health_checker(self) -> DatabaseHealthChecker:
        """Get the health checker"""
        return self.health_checker

    async def get_stats(self) -> dict[str, Any]:
        """Get comprehensive monitoring statistics"""
        query_stats = await self.query_monitor.get_stats()
        connection_stats = await self.collector.get_connection_stats()
        transaction_stats = await self.transaction_monitor.get_stats()

        return {
            "query_stats": query_stats,
            "connection_stats": connection_stats,
            "transaction_stats": transaction_stats,
            "timestamp": self._get_datetime(),
        }

    async def perform_health_check(
        self,
        connection_string: str,
        pool: Any = None,
    ) -> dict[str, Any]:
        """Perform comprehensive health check"""
        health_checks = []

        # Database connectivity check
        db_health = await self.health_checker.check_database_health(connection_string)
        health_checks.append(db_health)

        # Connection pool check (if pool provided)
        if pool:
            pool_health = await self.health_checker.check_connection_pool_health(pool)
            health_checks.append(pool_health)

        # Performance checks
        perf_checks = await self.health_checker.check_performance_health()
        health_checks.extend(perf_checks)

        # Aggregate status

        statuses = [check.status for check in health_checks]
        if "critical" in statuses:
            overall_status = "critical"
        elif "warning" in statuses:
            overall_status = "warning"
        elif "healthy" in statuses:
            overall_status = "healthy"
        else:
            overall_status = "unknown"

        return {
            "overall_status": overall_status,
            "checks": [
                {
                    "component": check.component,
                    "status": check.status,
                    "message": check.message,
                    "timestamp": check.timestamp.isoformat(),
                    "details": check.details,
                }
                for check in health_checks
            ],
            "timestamp": self._get_datetime().isoformat(),
        }
