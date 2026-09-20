"""HTTP request metrics middleware.

Captures per-request timing, status codes, and error rates via a
``MetricsCollectorProtocol`` protocol. Framework-native with no hard dependency
on Prometheus or any specific backend — the collector is injected.

Usage::

    from quadkit.web.middleware.metrics import MetricsMiddleware, InMemoryMetricsCollector

    # In-memory collector (useful for testing and dashboards)
    collector = InMemoryMetricsCollector()
    app.add_middleware(MetricsMiddleware, collector=collector)

    # Or use the WebConfig opt-in (WebProvider handles wiring automatically):
    web_config = WebConfig(enable_request_metrics=True)

Metrics tracked:
    - ``http_requests_total`` counter (labels: method, path, status)
    - ``http_request_duration_seconds`` histogram (labels: method, path)
    - ``http_requests_in_progress`` gauge (labels: method)
    - ``http_errors_total`` counter (labels: method, path, status)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

from starlette.routing import Match

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from starlette.types import ASGIApp, Receive, Scope, Send

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MetricsCollectorProtocol(Protocol):
    """Protocol for recording HTTP metrics.

    Implement this protocol and inject an instance into ``MetricsMiddleware``
    to plug in any metrics backend (Prometheus, OTEL, Datadog, etc.).
    """

    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric.

        Args:
            name: MetricProtocol name (e.g. ``"http_requests_total"``).
            value: Amount to increment by.
            labels: Dimension labels.
        """
        ...

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram observation.

        Args:
            name: MetricProtocol name (e.g. ``"http_request_duration_seconds"``).
            value: Observed value.
            labels: Dimension labels.
        """
        ...

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge to a specific value.

        Args:
            name: MetricProtocol name (e.g. ``"http_requests_in_progress"``).
            value: Gauge value.
            labels: Dimension labels.
        """
        ...


# ---------------------------------------------------------------------------
# In-memory implementation (testing / lightweight dashboards)
# ---------------------------------------------------------------------------


@dataclass
class MetricEntry:
    """Single serialisable metric snapshot."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)


class InMemoryMetricsCollector:
    """Thread-safe in-memory implementation of :class:`MetricsCollectorProtocol`.

    Ideal for unit tests and lightweight scenarios where an external metrics
    system is not available.

    All recorded values are accessible via :meth:`snapshot`.
    """

    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = defaultdict(float)

    # -- MetricsCollectorProtocol protocol --------------------------------------------

    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a named counter."""
        key = self._key(name, labels)
        self._counters[key] += value

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram observation."""
        key = self._key(name, labels)
        self._histograms[key].append(value)

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge value."""
        key = self._key(name, labels)
        self._gauges[key] = value

    # -- Inspection helpers ---------------------------------------------------

    def counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Return the current value of a counter.

        Args:
            name: MetricProtocol name.
            labels: Label filter.

        Returns:
            Counter value (0 if not recorded).
        """
        return self._counters.get(self._key(name, labels), 0.0)

    def histogram_values(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> list[float]:
        """Return all recorded histogram observations.

        Args:
            name: MetricProtocol name.
            labels: Label filter.

        Returns:
            List of recorded values.
        """
        return list(self._histograms.get(self._key(name, labels), []))

    def gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Return the current gauge value.

        Args:
            name: MetricProtocol name.
            labels: Label filter.

        Returns:
            Gauge value (0 if not set).
        """
        return self._gauges.get(self._key(name, labels), 0.0)

    def snapshot(self) -> dict[str, Any]:
        """Return a complete snapshot of all recorded metrics.

        Returns:
            Dictionary with ``counters``, ``histograms``, and ``gauges``.
        """
        return {
            "counters": dict(self._counters),
            "histograms": {k: list(v) for k, v in self._histograms.items()},
            "gauges": dict(self._gauges),
        }

    def reset(self) -> None:
        """Clear all recorded metrics. Useful between test runs."""
        self._counters.clear()
        self._histograms.clear()
        self._gauges.clear()

    @staticmethod
    def _key(name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class MetricsMiddleware:
    """Pure-ASGI HTTP metrics middleware.

    Tracks the following metrics for every HTTP request:

    - ``http_requests_total`` — counter labelled by method, path, status.
    - ``http_request_duration_seconds`` — histogram labelled by method, path.
    - ``http_requests_in_progress`` — gauge labelled by method.
    - ``http_errors_total`` — counter labelled by method, path, status (for 5xx).

    Paths are normalised using the Starlette route pattern (e.g.
    ``/users/{id}`` instead of ``/users/123``) to avoid high-cardinality
    series. Falls back to the raw path when no route is matched.

    Args:
        app: The ASGI application to wrap.
        collector: A :class:`MetricsCollectorProtocol` for recording metrics.
        filter_paths: Optional set of paths to skip (e.g. ``{"/health", "/metrics"}``).
    """

    def __init__(
        self,
        app: ASGIApp,
        collector: MetricsCollectorProtocol,
        filter_paths: set[str] | None = None,
    ) -> None:
        self.app = app
        self.collector = collector
        self.filter_paths: set[str] = filter_paths or {"/health", "/metrics"}
        self._in_progress: dict[str, int] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process a single ASGI request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "/")

        # Skip filtered paths
        if path in self.filter_paths:
            await self.app(scope, receive, send)
            return

        method: str = scope.get("method", "GET").upper()
        normalised_path = self._normalise_path(scope)

        # Track in-progress requests
        self._in_progress[method] = self._in_progress.get(method, 0) + 1
        self.collector.set_gauge(
            "http_requests_in_progress",
            float(self._in_progress[method]),
            {"method": method},
        )

        start = time.perf_counter()
        status_code = 500  # default — overwritten when response starts

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            status_str = str(status_code)

            labels = {"method": method, "path": normalised_path, "status": status_str}

            self.collector.increment_counter("http_requests_total", labels=labels)
            self.collector.observe_histogram(
                "http_request_duration_seconds",
                duration,
                labels={"method": method, "path": normalised_path},
            )

            # Decrement in-progress gauge
            self._in_progress[method] = max(0, self._in_progress.get(method, 1) - 1)
            self.collector.set_gauge(
                "http_requests_in_progress",
                float(self._in_progress[method]),
                {"method": method},
            )

            # Track server-side errors separately
            if status_code >= 500:
                self.collector.increment_counter(
                    "http_errors_total",
                    labels=labels,
                )

    def _normalise_path(self, scope: Scope) -> str:
        """Return the matched route pattern or the raw path.

        Uses Starlette's router to resolve ``/users/123`` → ``/users/{id}``.
        Falls back to the literal path if no route matches.
        """
        router = scope.get("app")
        if router is not None and hasattr(router, "router"):
            router = router.router  # unwrap Starlette app
        if router is not None and hasattr(router, "routes"):
            for route in router.routes:
                match, _ = route.matches(scope)
                if match == Match.FULL and hasattr(route, "path"):
                    return str(route.path)
        return cast("str", scope.get("path", "/"))


__all__ = [
    "InMemoryMetricsCollector",
    "MetricsCollectorProtocol",
    "MetricsMiddleware",
]
