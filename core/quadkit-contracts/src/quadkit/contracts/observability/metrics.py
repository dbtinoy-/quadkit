"""Monitoring protocols.

Protocols for metrics, tracing, and health checking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.core.health import HealthCheckCategory

if TYPE_CHECKING:
    from collections.abc import Callable


@runtime_checkable
class AlertDispatcherProtocol(Protocol):
    """Protocol for dispatching operational alerts.

    Implementations route alerts to notification channels (logging,
    PagerDuty, Slack, etc.).  ``the optional provider`` ships a built-in
    :class:`~the optional provider module` that writes
    alerts to the structured logger.

    Example::

        class SlackAlertDispatcher:
            async def send_alert(
                self,
                title: str,
                message: str,
                severity: str,
                context: dict[str, Any] | None = None,
            ) -> None:
                await self._slack.post(
                    channel="#ops",
                    text=f"[{severity}] {title}: {message}",
                )
    """

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch a free-form operational alert.

        Args:
            title: Short, human-readable alert title.
            message: Detailed alert message.
            severity: Severity level string, e.g. ``"low"``, ``"high"``,
                ``"critical"``.
            context: Optional free-form mapping of additional metadata.
        """
        ...

    async def send_metric_alert(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch an alert triggered by a metric threshold breach.

        Args:
            metric_name: Name of the metric that breached its threshold.
            current_value: Observed metric value at the time of the alert.
            threshold: The configured threshold that was exceeded.
            context: Optional free-form mapping of additional metadata.
        """
        ...


@runtime_checkable
class MetricsRecorderProtocol(Protocol):
    """Record pre-defined metrics. Minimal interface for resilience, events, etc."""

    def increment(
        self,
        name: str,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric.

        Args:
            name: MetricProtocol name.
            value: Value to increment by.
            tags: Optional tags/labels.
        """
        ...

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric.

        Args:
            name: MetricProtocol name.
            value: Current value.
            tags: Optional tags/labels.
        """
        ...

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram value.

        Args:
            name: MetricProtocol name.
            value: Value to record.
            tags: Optional tags/labels.
        """
        ...


@runtime_checkable
class MetricsFactoryProtocol(Protocol):
    """Create metric instruments. Extended interface for the optional provider."""

    def register_metric(self, metric: MetricProtocol) -> None:
        """Register an existing metric instrument.

        Args:
            metric: Pre-defined metric instance.
        """
        ...

    def create_counter(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> Any:
        """Create a counter metric.

        Args:
            name: MetricProtocol name.
            description: MetricProtocol description.
            labels: Default labels.

        Returns:
            Counter metric instance.
        """
        ...

    def create_gauge(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> Any:
        """Create a gauge metric.

        Args:
            name: MetricProtocol name.
            description: MetricProtocol description.
            labels: Default labels.

        Returns:
            Gauge metric instance.
        """
        ...

    def create_histogram(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
        buckets: list[float] | None = None,
    ) -> Any:
        """Create a histogram metric.

        Args:
            name: MetricProtocol name.
            description: MetricProtocol description.
            labels: Default labels.
            buckets: Histogram buckets.

        Returns:
            Histogram metric instance.
        """
        ...


@runtime_checkable
class MetricProtocol(Protocol):
    """Protocol for metric implementations.

    Metrics track numeric measurements over time.
    """

    @property
    def name(self) -> str:
        """MetricProtocol name."""
        ...

    @property
    def description(self) -> str:
        """MetricProtocol description."""
        ...

    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a metric value.

        Args:
            value: Numeric value to record.
            labels: Optional labels/tags.
        """
        ...


@runtime_checkable
class MetricsBackendProtocol(Protocol):
    """Protocol for metrics backend implementations (metrics only).

    Backends export metrics to external systems.
    """

    async def initialize(self) -> None:
        """Initialize the metrics backend."""
        ...

    async def shutdown(self) -> None:
        """Shutdown the metrics backend."""
        ...

    def record_metric(
        self,
        name: str,
        value: Any,
        metric_type: str,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a metric value.

        Args:
            name: MetricProtocol name.
            value: MetricProtocol value.
            metric_type: Type of metric (counter, gauge, histogram).
            labels: Optional labels.
        """
        ...


@runtime_checkable
class MetricsCollectorProtocol(
    MetricsRecorderProtocol, MetricsFactoryProtocol, Protocol
):
    """Full metrics capability. Implemented by the optional provider.

    Combines recording capabilities (increment, gauge, histogram) with
    factory capabilities (create_counter, create_gauge, create_histogram).
    """


@runtime_checkable
class HealthCheckRegistryProtocol(Protocol):
    """Protocol for a categorised health check registry.

    Implementations (e.g. ``HealthChecker``) store checks tagged with a
    :class:`~quadkit.contracts.core.health.HealthCheckCategory` so that
    callers can query subsets independently:

    * ``run_liveness``  — is the process alive and not deadlocked?
    * ``run_readiness`` — is the process ready to accept traffic?
    * ``run_startup``   — has initial startup completed?

    This maps directly to the three Kubernetes probe types.
    """

    def add(
        self,
        name: str,
        check: Callable[[], Any],
        *,
        timeout: float | None = None,
        critical: bool = True,
        category: HealthCheckCategory = HealthCheckCategory.READINESS,
    ) -> None:
        """Register a categorised health check.

        Args:
            name: Unique identifier for the check.
            check: Callable that performs the check.
            timeout: Optional per-check timeout in seconds.
            critical: Whether a non-healthy result should make the aggregate
                readiness status ``UNHEALTHY``. Defaults to ``True``.
            category: :class:`~quadkit.contracts.core.health.HealthCheckCategory`
                value. Defaults to ``READINESS``.
        """
        ...

    async def run_all(self) -> tuple[Any, dict[str, Any]]:
        """Run all registered checks regardless of category.

        Returns:
            ``(aggregate_status, per_check_results)`` tuple.
        """
        ...

    async def run_liveness(self) -> tuple[Any, dict[str, Any]]:
        """Run only LIVENESS checks.

        Returns:
            ``(aggregate_status, per_check_results)`` tuple.
        """
        ...

    async def run_readiness(self) -> tuple[Any, dict[str, Any]]:
        """Run only READINESS checks.

        Returns:
            ``(aggregate_status, per_check_results)`` tuple.
        """
        ...

    async def run_startup(self) -> tuple[Any, dict[str, Any]]:
        """Run only STARTUP checks.

        Returns:
            ``(aggregate_status, per_check_results)`` tuple.
        """
        ...


__all__ = [
    "AlertDispatcherProtocol",
    "HealthCheckRegistryProtocol",
    "MetricProtocol",
    "MetricsBackendProtocol",
    "MetricsCollectorProtocol",
    "MetricsFactoryProtocol",
    "MetricsRecorderProtocol",
]
