"""Metric-recording convenience methods."""

from __future__ import annotations

from typing import Any, cast

from quadkit.contracts.core import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.contracts.observability.metrics import (
    MetricsCollectorProtocol as MetricsCollectorProtocol,
)
from quadkit.contracts.observability.tracing import (
    TracerProtocol as TracerProtocol,
)
from quadkit.logging import get_logger
from quadkit.monitor.di._attrs import _MonitorAttrsMixin
from quadkit.monitor.health.sanitize import safe_error_message

logger = get_logger(__name__)

_HOOK_PACKAGE_BY_NAME = {
    "cache.hit": "cache",
    "cache.miss": "cache",
    "cache.evicted": "cache",
    "event.published": "events",
    "event.handled": "events",
    "connection.acquired": "sql",
    "transaction.begin": "sql",
    "transaction.end": "sql",
    "request.received": "web",
    "response.prepared": "web",
    "server.started": "web",
    "server.stopped": "web",
    "auth.login": "auth",
    "auth.logout": "auth",
    "token.refreshed": "auth",
    "message.published": "queue",
    "message.consumed": "queue",
    "task.queued": "tasks",
    "task.completed": "tasks",
    "task.failed": "tasks",
}
_HOOK_EVENT_COUNTER_NAME = "quadkit_hook_events_total"


class _MonitorMetricsMixin(_MonitorAttrsMixin):
    """See :class:`MonitorProvider`."""

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check monitoring provider health"""
        details = {
            "message": "Monitoring provider is active",
            "backend_type": type(self.backend).__name__,
            "metrics_count": len(self.metrics_collector.get_all_metrics()),
        }

        # If we have a backend and it has a health_check, try to use it
        # Avoid delegation if backend is a generic Mock from tests
        from unittest.mock import Mock

        if (
            hasattr(self.backend, "health_check")
            and not isinstance(self.backend, Mock)
            and callable(self.backend.health_check)
        ):
            try:
                backend_health = await cast("Any", self.backend).health_check()
                # Merge backend details if possible
                if hasattr(backend_health, "details") and isinstance(
                    backend_health.details, dict
                ):
                    details.update(cast("dict[str, Any]", backend_health.details))
                return cast("HealthCheckResult", backend_health)
            except Exception as e:  # noqa: BLE001 — a failed monitor health check reports UNHEALTHY, never raises
                logger.warning(
                    "monitor_health_check_failed",
                    component="monitor",
                    error=str(e),
                )
                return HealthCheckResult(
                    component="monitor",
                    status=HealthStatus.UNHEALTHY,
                    error=safe_error_message(e),
                    details=details,
                    category=HealthCheckCategory.READINESS,
                )

        return HealthCheckResult(
            component="monitor",
            status=HealthStatus.HEALTHY,
            details=details,
            category=HealthCheckCategory.READINESS,
        )

    def record_request(
        self,
        method: str,
        path: str,
        duration: float,
        status_code: int,
    ) -> None:
        """Record an HTTP request"""
        # Ensure metrics exist
        self._ensure_request_metrics()

        # Record metrics
        counter = self.metrics_collector.get_metric("quadkit_requests_total")
        if counter:
            cast("Any", counter).increment(
                labels={"method": method, "status": str(status_code)},
            )

        histogram = self.metrics_collector.get_metric(
            "quadkit_request_duration_seconds",
        )
        if histogram:
            cast("Any", histogram).observe(duration, labels={"method": method})

    def _ensure_request_metrics(self) -> None:
        """Ensure request metrics are created"""
        if not self.metrics_collector.get_metric("quadkit_requests_total"):
            self.metrics_collector.create_counter(
                "quadkit_requests_total",
                "Total number of requests",
                labels={"method": "", "status": ""},
            )

        if not self.metrics_collector.get_metric("quadkit_request_duration_seconds"):
            self.metrics_collector.create_histogram(
                "quadkit_request_duration_seconds",
                "Request duration in seconds",
                labels={"method": ""},
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            )

    def record_connection_change(self, delta: int) -> None:
        """Record connection count change"""
        gauge = self.metrics_collector.get_metric("quadkit_active_connections")
        if gauge:
            cast("Any", gauge).increment(delta)

    def create_counter(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> Any:
        """Create a counter metric"""
        return self.metrics_collector.create_counter(name, description, labels)

    def create_gauge(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> Any:
        """Create a gauge metric"""
        return self.metrics_collector.create_gauge(name, description, labels)

    def create_histogram(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
        buckets: list[float] | None = None,
    ) -> Any:
        """Create a histogram metric"""
        return self.metrics_collector.create_histogram(
            name,
            description,
            labels,
            buckets,
        )


__all__ = ["_MonitorMetricsMixin"]
