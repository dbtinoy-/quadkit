"""Prometheus backend — the single public Prometheus integration for Quadkit Monitor.

:class:`PrometheusBackend` is the canonical way to wire Prometheus into a
Quadkit application.  It implements the :class:`~quadkit.contracts.observability.MetricsBackendProtocol`
protocol and, on :meth:`initialize`, starts the ``prometheus_client`` HTTP
exposition server so that a scraper can pull metrics from the configured port.

For ASGI deployments that need to serve the ``/metrics`` endpoint inside the
same process as the web application (rather than on a separate port), use
:class:`~quadkit.monitor.backends.exporters.PrometheusMetricsExporter` instead.

**Internal detail**: metric object creation and registry management are handled
by :class:`~quadkit.monitor.metrics.prometheus.PrometheusExporter`, which is an
internal utility not intended for direct use outside this package.
"""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.contracts.observability.metrics import MetricsBackendProtocol
from quadkit.logging import get_logger
from quadkit.monitor.exceptions import BackendNotAvailableError
from quadkit.monitor.tracing import Span, SpanContext

logger = get_logger(__name__)

# Predeclare optional names as Any to keep static analysis consistent
PromCounter: Any = None
PromGauge: Any = None
PromHistogram: Any = None
start_http_server: Any = None

try:
    from prometheus_client import Counter as _PC  # noqa: N814
    from prometheus_client import Gauge as _PG  # noqa: N814
    from prometheus_client import Histogram as _PH  # noqa: N814
    from prometheus_client import start_http_server as _SHS  # noqa: N812

    PromCounter = _PC
    PromGauge = _PG
    PromHistogram = _PH
    start_http_server = _SHS
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


class PrometheusBackend(MetricsBackendProtocol):
    """Prometheus monitoring backend."""

    def __init__(self, port: int = 8000):
        """Initialize Prometheus backend.

        Args:
            port: Port for metrics HTTP server

        Raises:
            BackendNotAvailableError: If prometheus-client is not installed
        """
        if not HAS_PROMETHEUS:
            raise BackendNotAvailableError(
                "prometheus-client is required for Prometheus backend. "
                "Install with: pip install quadkit-monitor[prometheus]",
            )

        self.port = port
        self._metrics: dict[str, Any] = {}
        self._server_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize Prometheus metrics server.

        If the configured port is already in use, log a warning and continue
        without failing the entire application startup.
        """
        try:
            await asyncio.to_thread(start_http_server, self.port)
        except OSError as e:
            # Address already in use or other socket errors should not fail app startup
            logger.warning(
                "Prometheus metrics server could not be started on port %s: %s",
                self.port,
                e,
            )
        except Exception:  # defensive catch to avoid breaking app startup # noqa: BLE001 — the metrics server is optional
            # Any other errors - log and continue to avoid breaking app startup
            logger.exception(
                "Unexpected error while starting Prometheus metrics server; continuing without Prometheus",
            )

    async def shutdown(self) -> None:
        """Shutdown Prometheus server."""
        # Prometheus server runs in background, no explicit shutdown needed

    def record_metric(
        self,
        name: str,
        value: Any,
        metric_type: str,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a metric using Prometheus.

        Args:
            name: MetricProtocol name
            value: MetricProtocol value
            metric_type: Type of metric (counter, gauge, histogram)
            labels: Optional metric labels
        """
        labels = labels or {}

        if metric_type == "counter":
            if name not in self._metrics:
                self._metrics[name] = PromCounter(
                    name,
                    f"Counter: {name}",
                    labelnames=list(labels.keys()),
                )
            self._metrics[name].labels(**labels).inc(value)
        elif metric_type == "gauge":
            if name not in self._metrics:
                self._metrics[name] = PromGauge(
                    name,
                    f"Gauge: {name}",
                    labelnames=list(labels.keys()),
                )
            self._metrics[name].labels(**labels).set(value)
        elif metric_type == "histogram":
            if name not in self._metrics:
                self._metrics[name] = PromHistogram(
                    name,
                    f"Histogram: {name}",
                    labelnames=list(labels.keys()),
                )
            self._metrics[name].labels(**labels).observe(value)

    def create_span(self, name: str, parent_context: SpanContext | None = None) -> Span:
        """Create a span (Prometheus doesn't do tracing, so this is a no-op).

        Args:
            name: Span name
            parent_context: Optional parent span context

        Returns:
            Dummy span instance
        """
        import time

        context = SpanContext(trace_id="prometheus-no-trace", span_id=name)
        return Span(name=name, context=context, start_time=time.time())
