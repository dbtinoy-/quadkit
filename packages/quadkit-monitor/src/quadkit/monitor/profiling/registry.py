from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.monitor.profiling.models import PerformanceMetrics


class ProfilingRegistry:
    """Thin last-value store for profiling metrics.

    Holds the most recently recorded :class:`PerformanceMetrics` snapshot
    and the name of the operation that produced it.  This is intentionally
    minimal — it is **not** a history buffer and is suitable only for
    exposing the latest profiling result to tooling (e.g. admin dashboards
    or health checks).

    .. note::
        This class holds mutable state and must be registered as a
        container-managed singleton via :class:`MonitorProvider`.  Do **not**
        instantiate it directly in application code; resolve it from the DI
        container instead.

    Attributes:
        _last_metrics: The most recently stored metrics, or ``None``.
        _last_operation_name: Name of the operation that produced the metrics.
    """

    def __init__(self) -> None:
        self._last_metrics: PerformanceMetrics | None = None
        self._last_operation_name: str | None = None

    def update_last_metrics(
        self,
        metrics: PerformanceMetrics,
        operation_name: str,
    ) -> None:
        """Store the latest profiling snapshot.

        Args:
            metrics: The performance metrics to store.
            operation_name: Human-readable name of the profiled operation.
        """
        self._last_metrics = metrics
        self._last_operation_name = operation_name

    def get_last_metrics(self) -> PerformanceMetrics | None:
        """Return the most recently stored metrics, or ``None``."""
        return self._last_metrics

    def get_last_operation_name(self) -> str | None:
        """Return the name of the most recently profiled operation, or ``None``."""
        return self._last_operation_name

    def clear(self) -> None:
        """Reset stored state (useful between test cases)."""
        self._last_metrics = None
        self._last_operation_name = None
