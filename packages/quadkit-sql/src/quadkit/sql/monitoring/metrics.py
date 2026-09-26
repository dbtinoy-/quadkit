"""Database monitoring metrics and data structures"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

# Import unified health status from core quadkit
from quadkit.contracts.core import HealthStatus as UnifiedHealthStatus
from quadkit.primitives import clock as ambient_clock


@dataclass
class QueryMetrics:
    """Metrics for a database query"""

    query: str
    parameters: list[Any] | None
    execution_time: float
    timestamp: datetime
    success: bool
    error_message: str | None = None
    connection_id: str | None = None
    transaction_id: str | None = None


@dataclass
class ConnectionMetrics:
    """Metrics for database connections"""

    active_connections: int
    total_connections: int
    available_connections: int
    checked_out_connections: int
    checked_in_connections: int
    utilization: float
    timestamp: datetime


@dataclass
class TransactionMetrics:
    """Metrics for database transactions"""

    transaction_id: str
    start_time: datetime
    end_time: datetime | None
    duration: float | None
    operation: str  # 'commit', 'rollback', 'savepoint', etc.
    success: bool
    deadlock_detected: bool
    error_message: str | None = None
    nested_level: int = 0


@dataclass
class PerformanceBaseline:
    """Performance baseline for monitoring"""

    metric_name: str
    expected_value: float
    warning_threshold: float
    critical_threshold: float
    unit: str
    description: str


@dataclass
class HealthStatus:
    """Health status for database components"""

    component: str
    status: UnifiedHealthStatus
    message: str
    timestamp: datetime
    details: dict[str, Any] | None = None


@runtime_checkable
class DbMetricsCollector(Protocol):
    """Protocol for database metrics collectors."""

    async def record_query_metrics(self, metrics: QueryMetrics) -> None:
        """Record query execution metrics."""
        ...

    async def record_connection_metrics(self, metrics: ConnectionMetrics) -> None:
        """Record connection pool metrics."""
        ...

    async def get_query_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Get query statistics for the given time range."""
        ...

    async def record_transaction_metrics(self, metrics: TransactionMetrics) -> None:
        """Record transaction execution metrics."""
        ...

    async def get_transaction_stats(
        self,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Get transaction statistics for the given time range."""
        ...

    async def get_connection_stats(
        self,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Get connection pool statistics for the given time range."""
        ...

    async def get_performance_baselines(self) -> list[PerformanceBaseline]:
        """Get performance baselines."""
        ...

    async def set_performance_baseline(self, baseline: PerformanceBaseline) -> None:
        """Set a performance baseline."""
        ...


class InMemoryDbMetricsCollector(DbMetricsCollector):
    """In-memory metrics collector for development"""

    MAX_QUERY_LENGTH: int = 512

    def __init__(
        self,
        max_metrics: int = 10000,
    ):
        self.max_metrics = max_metrics
        self.query_metrics: list[QueryMetrics] = []
        self.connection_metrics: list[ConnectionMetrics] = []
        self.transaction_metrics: list[TransactionMetrics] = []
        self.performance_baselines: dict[str, PerformanceBaseline] = {}
        self._init_default_baselines()

    def _now(self) -> datetime:
        """Get current UTC time from ambient clock."""
        return ambient_clock.now()

    async def record_query_metrics(self, metrics: QueryMetrics) -> None:
        """Record query execution metrics, truncating long query strings."""
        if len(metrics.query) > self.MAX_QUERY_LENGTH:
            metrics = dataclasses.replace(
                metrics,
                query=metrics.query[: self.MAX_QUERY_LENGTH] + "…",
                parameters=None,
            )
        self.query_metrics.append(metrics)
        if len(self.query_metrics) > self.max_metrics:
            self.query_metrics.pop(0)

    async def record_connection_metrics(self, metrics: ConnectionMetrics) -> None:
        """Record connection pool metrics"""
        self.connection_metrics.append(metrics)
        if len(self.connection_metrics) > self.max_metrics:
            self.connection_metrics.pop(0)

    async def get_query_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Get query statistics"""

        cutoff_time = self._now().timestamp() - time_range_seconds
        recent_metrics = list(
            filter(lambda m: m.timestamp.timestamp() > cutoff_time, self.query_metrics),
        )

        if not recent_metrics:
            return {
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "average_execution_time": 0.0,
                "slowest_query": None,
                "query_count_by_type": {},
            }

        successful = list(filter(lambda m: m.success, recent_metrics))
        failed = list(filter(lambda m: not m.success, recent_metrics))

        execution_times = [m.execution_time for m in recent_metrics]
        avg_time = sum(execution_times) / len(execution_times)

        slowest = max(recent_metrics, key=lambda m: m.execution_time)

        # Simple query type classification
        query_types: dict[str, int] = {}
        for metric in recent_metrics:
            query_type = metric.query.strip().split()[0].upper()
            query_types[query_type] = query_types.get(query_type, 0) + 1

        return {
            "total_queries": len(recent_metrics),
            "successful_queries": len(successful),
            "failed_queries": len(failed),
            "average_execution_time": avg_time,
            "slowest_query": {
                "query": slowest.query,
                "execution_time": slowest.execution_time,
                "timestamp": slowest.timestamp,
            },
            "query_count_by_type": query_types,
        }

    async def record_transaction_metrics(self, metrics: TransactionMetrics) -> None:
        """Record transaction execution metrics"""
        self.transaction_metrics.append(metrics)
        if len(self.transaction_metrics) > self.max_metrics:
            self.transaction_metrics.pop(0)

    async def get_transaction_stats(
        self,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Get transaction statistics"""

        cutoff_time = self._now().timestamp() - time_range_seconds
        recent_metrics = list(
            filter(
                lambda m: m.start_time.timestamp() > cutoff_time,
                self.transaction_metrics,
            ),
        )

        if not recent_metrics:
            return {
                "total_transactions": 0,
                "successful_transactions": 0,
                "failed_transactions": 0,
                "deadlock_count": 0,
                "commit_count": 0,
                "rollback_count": 0,
                "average_duration": 0.0,
                "commit_ratio": 0.0,
            }

        successful = list(filter(lambda m: m.success, recent_metrics))
        failed = list(filter(lambda m: not m.success, recent_metrics))
        deadlocks = list(filter(lambda m: m.deadlock_detected, recent_metrics))
        commits = list(filter(lambda m: m.operation == "commit", recent_metrics))
        rollbacks = list(filter(lambda m: m.operation == "rollback", recent_metrics))

        durations = [m.duration for m in recent_metrics if m.duration is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        commit_ratio = len(commits) / len(recent_metrics) if recent_metrics else 0.0

        return {
            "total_transactions": len(recent_metrics),
            "successful_transactions": len(successful),
            "failed_transactions": len(failed),
            "deadlock_count": len(deadlocks),
            "commit_count": len(commits),
            "rollback_count": len(rollbacks),
            "average_duration": avg_duration,
            "commit_ratio": commit_ratio,
        }

    async def get_connection_stats(
        self,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Get connection pool statistics"""

        cutoff_time = self._now().timestamp() - time_range_seconds
        recent_metrics = list(
            filter(
                lambda m: m.timestamp.timestamp() > cutoff_time,
                self.connection_metrics,
            ),
        )

        if not recent_metrics:
            return {
                "total_samples": 0,
                "average_active_connections": 0.0,
                "average_utilization": 0.0,
                "max_utilization": 0.0,
                "min_utilization": 0.0,
                "current_active_connections": 0,
                "current_total_connections": 0,
                "current_utilization": 0.0,
            }

        # Calculate averages
        active_connections = [m.active_connections for m in recent_metrics]
        utilizations = [m.utilization for m in recent_metrics]

        avg_active = sum(active_connections) / len(active_connections)
        avg_utilization = sum(utilizations) / len(utilizations)
        max_utilization = max(utilizations)
        min_utilization = min(utilizations)

        # Current values (most recent)
        current = recent_metrics[-1]

        return {
            "total_samples": len(recent_metrics),
            "average_active_connections": avg_active,
            "average_utilization": avg_utilization,
            "max_utilization": max_utilization,
            "min_utilization": min_utilization,
            "current_active_connections": current.active_connections,
            "current_total_connections": current.total_connections,
            "current_utilization": current.utilization,
        }

    async def get_performance_baselines(self) -> list[PerformanceBaseline]:
        """Get performance baselines"""
        return list(self.performance_baselines.values())

    async def set_performance_baseline(self, baseline: PerformanceBaseline) -> None:
        """Set a performance baseline"""
        self.performance_baselines[baseline.metric_name] = baseline

    def _init_default_baselines(self) -> None:
        """Initialize default performance baselines"""
        defaults = [
            PerformanceBaseline(
                metric_name="query_execution_time",
                expected_value=0.1,
                warning_threshold=0.5,
                critical_threshold=2.0,
                unit="seconds",
                description="Average query execution time",
            ),
            PerformanceBaseline(
                metric_name="connection_pool_utilization",
                expected_value=0.7,
                warning_threshold=0.85,
                critical_threshold=0.95,
                unit="ratio",
                description="Connection pool utilization ratio",
            ),
            PerformanceBaseline(
                metric_name="transaction_commit_ratio",
                expected_value=0.95,
                warning_threshold=0.85,
                critical_threshold=0.7,
                unit="ratio",
                description="Ratio of successful transaction commits",
            ),
            PerformanceBaseline(
                metric_name="deadlock_rate",
                expected_value=0.001,
                warning_threshold=0.01,
                critical_threshold=0.05,
                unit="ratio",
                description="Rate of deadlock occurrences",
            ),
        ]

        for baseline in defaults:
            self.performance_baselines[baseline.metric_name] = baseline
