"""Core no-op observability primitives for Quadkit Framework.

These implementations satisfy the observability contracts without requiring
``quadkit-monitor``. They are intentionally lightweight and safe to keep as
long-lived singletons in the container.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Self

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.observability.metrics import MetricProtocol
from quadkit.contracts.observability.tracing import SpanProtocol


class NoOpSpan:
    """No-op span that silently drops all tracing operations."""

    __slots__ = ("attributes", "context", "name")

    def __init__(self, name: str = "") -> None:
        self.name = name
        self.attributes: dict[str, Any] = {}
        self.context: tuple[str, str] = ("", "")

    def set_attribute(self, key: str, value: Any) -> None:
        """Store span attributes for introspection in tests."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Ignore span events."""

    def record_exception(self, exception: Exception) -> None:
        """Ignore recorded exceptions."""

    def set_status(self, status: str) -> None:
        """Ignore span status updates."""

    def end(self) -> None:
        """Mark the span as ended without side effects."""

    def __enter__(self) -> Self:
        """Support context manager usage."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Ignore context manager exit signals."""


class NoOpTracer:
    """No-op tracer that returns :class:`NoOpSpan` instances."""

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        context: Any | None = None,
    ) -> NoOpSpan:
        """Start a no-op span."""
        span = NoOpSpan(name)
        if attributes:
            span.attributes.update(attributes)
        return span

    def get_current_span(self) -> SpanProtocol | None:
        """Return no active span."""
        return None

    def inject_context(
        self,
        carrier: dict[str, str],
        context: Any | None = None,
    ) -> None:
        """Leave the carrier unchanged."""

    def extract_context(self, carrier: dict[str, str]) -> Any | None:
        """Return no extracted context."""
        return None


class NoOpMetricsCollector:
    """Metrics collector that drops all observations."""

    def __init__(self) -> None:
        self._metrics: dict[str, MetricProtocol] = {}

    @property
    def name(self) -> str:
        """Return a placeholder metric name."""
        return "noop"

    @property
    def description(self) -> str:
        """Return a placeholder metric description."""
        return "No-op metrics collector"

    def register_metric(self, metric: MetricProtocol) -> None:
        """Ignore pre-created metrics."""

    def increment(
        self,
        name: str,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Ignore counter increments."""

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Ignore gauge values."""

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Ignore histogram samples."""

    def create_counter(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> NoOpMetricsCollector:
        """Return the collector itself."""
        return self

    def create_gauge(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> NoOpMetricsCollector:
        """Return the collector itself."""
        return self

    def create_histogram(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
        buckets: list[float] | None = None,
    ) -> NoOpMetricsCollector:
        """Return the collector itself."""
        return self

    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Ignore recorded metric values."""


class NoOpHealthCheckRegistry:
    """No-op registry for categorised health checks."""

    def add(
        self,
        name: str,
        check: Callable[[], Any],
        *,
        timeout: float | None = None,
        critical: bool = True,
        category: Any = None,
    ) -> None:
        """Ignore health check registration."""

    async def run_all(self) -> tuple[Any, dict[str, Any]]:
        """Return an empty aggregate result."""
        return HealthStatus.UNKNOWN, {}

    async def run_liveness(self) -> tuple[Any, dict[str, Any]]:
        """Return an empty liveness result."""
        return HealthStatus.UNKNOWN, {}

    async def run_readiness(self) -> tuple[Any, dict[str, Any]]:
        """Return an empty readiness result."""
        return HealthStatus.UNKNOWN, {}

    async def run_startup(self) -> tuple[Any, dict[str, Any]]:
        """Return an empty startup result."""
        return HealthStatus.UNKNOWN, {}

    async def health_check(self) -> HealthCheckResult:
        """Report the no-op registry as healthy."""
        return HealthCheckResult(component="noop", status=HealthStatus.HEALTHY)


class NoOpMetricsBackend:
    """No-op metrics backend used as a fallback when nothing is configured."""

    async def initialize(self) -> None:
        """Do nothing."""

    async def shutdown(self) -> None:
        """Do nothing."""

    def record_metric(
        self,
        name: str,
        value: Any,
        metric_type: str,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Ignore recorded metric values."""


__all__ = [
    "NoOpHealthCheckRegistry",
    "NoOpMetricsBackend",
    "NoOpMetricsCollector",
    "NoOpSpan",
    "NoOpTracer",
]
