"""Internal Prometheus metric registry utility for Quadkit Monitor.

.. internal::
    This module is **not** part of the public API.  It is infrastructure used
    exclusively by :class:`quadkit.monitor.backends.prometheus.PrometheusBackend`
    to get-or-create ``prometheus_client`` metric objects against an isolated
    :class:`prometheus_client.CollectorRegistry`.

    Do **not** import :class:`PrometheusExporter` directly from application code.
    Use :class:`~quadkit.monitor.backends.prometheus.PrometheusBackend` (for an
    HTTP-serving backend) or
    :class:`~quadkit.monitor.backends.exporters.PrometheusMetricsExporter` (for
    ASGI-compatible scrape endpoints) instead.
"""

from __future__ import annotations

from typing import Any

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Summary,
        generate_latest,
    )
except ImportError:
    CollectorRegistry = None
    Counter = None
    Gauge = None
    Histogram = None
    Summary = None

    def generate_latest() -> bytes:
        return b""

    CONTENT_TYPE_LATEST = "text/plain"


class PrometheusExporter:
    """Exporter for Prometheus-compatible metrics."""

    def __init__(self, registry: Any = None):
        self.registry = registry or (
            CollectorRegistry() if bool(CollectorRegistry) else None
        )
        self._metrics: dict[str, Any] = {}

    def get_or_create_counter(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Any:
        if not bool(Counter):
            return None
        if name not in self._metrics:
            self._metrics[name] = Counter(
                name,
                description,
                labels or [],
                registry=self.registry,
            )
        return self._metrics[name]

    def get_or_create_gauge(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Any:
        if not bool(Gauge):
            return None
        if name not in self._metrics:
            self._metrics[name] = Gauge(
                name,
                description,
                labels or [],
                registry=self.registry,
            )
        return self._metrics[name]

    def get_or_create_histogram(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> Any:
        if not bool(Histogram):
            return None
        if name not in self._metrics:
            kwargs: dict[str, Any] = {"registry": self.registry}
            if buckets:
                kwargs["buckets"] = buckets
            self._metrics[name] = Histogram(name, description, labels or [], **kwargs)
        return self._metrics[name]

    def get_or_create_summary(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Any:
        if not bool(Summary):
            return None
        if name not in self._metrics:
            self._metrics[name] = Summary(
                name,
                description,
                labels or [],
                registry=self.registry,
            )
        return self._metrics[name]

    def export(self) -> bytes:
        """Export all metrics in Prometheus format."""
        if not bool(self.registry) or not bool(generate_latest):
            return b""
        return bytes(generate_latest(self.registry))

    @property
    def content_type(self) -> str:
        return str(CONTENT_TYPE_LATEST)


exporter = PrometheusExporter()


def get_prometheus_exporter() -> PrometheusExporter:
    """Get the Prometheus exporter instance."""
    return exporter
