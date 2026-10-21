from __future__ import annotations

from quadkit.contracts.observability.metrics import MetricProtocol
from quadkit.monitor.metrics.counter import Counter
from quadkit.monitor.metrics.gauge import Gauge
from quadkit.monitor.metrics.histogram import Histogram
from quadkit.monitor.metrics.summary import Summary

#: The process-wide collector the monitor provider installs at registration
#: time. Middleware is constructed by the web layer with no access to the DI
#: container (Starlette instantiates it while building the stack), so it needs
#: a way to reach the *same* collector the application's services record into;
#: two collectors would mean a scrape endpoint that reports nothing.
_default_collector: MetricsCollectorProtocol | None = None


def get_default_collector() -> MetricsCollectorProtocol:
    """Return the process-wide metrics collector, creating it on first use."""
    global _default_collector  # noqa: PLW0603 — process-wide singleton by design
    if _default_collector is None:
        _default_collector = MetricsCollectorProtocol()
    return _default_collector


def set_default_collector(collector: MetricsCollectorProtocol) -> None:
    """Install *collector* as the process-wide collector (idempotent)."""
    global _default_collector  # noqa: PLW0603 — process-wide singleton by design
    _default_collector = collector


class MetricsCollectorProtocol:
    """Central metrics collection and reporting."""

    def __init__(self) -> None:
        self._metrics: dict[str, MetricProtocol] = {}

    def register_metric(self, metric: MetricProtocol) -> None:
        """Register an existing metric instrument."""
        self._metrics[metric.name] = metric

    def create_counter(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> Counter:
        counter = Counter(name, description, labels)
        self._metrics[name] = counter
        return counter

    def create_gauge(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> Gauge:
        gauge = Gauge(name, description, labels)
        self._metrics[name] = gauge
        return gauge

    def create_summary(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> Summary:
        summary = Summary(name, description, labels)
        self._metrics[name] = summary
        return summary

    def create_histogram(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram:
        histogram = Histogram(name, description, labels, buckets)
        self._metrics[name] = histogram
        return histogram

    def get_metric(self, name: str) -> MetricProtocol | None:
        return self._metrics.get(name)

    def get_all_metrics(self) -> dict[str, MetricProtocol]:
        return self._metrics.copy()

    def clear(self) -> None:
        self._metrics.clear()

    def increment(
        self,
        name: str,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric."""
        metric = self._metrics.get(name)
        if metric is None:
            metric = self.create_counter(name, labels=tags)
        if hasattr(metric, "increment"):
            import typing

            typing.cast("typing.Any", metric).increment(value, tags)
        elif hasattr(metric, "record"):
            metric.record(value, tags)

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric."""
        metric = self._metrics.get(name)
        if metric is None:
            metric = self.create_gauge(name, labels=tags)
        if hasattr(metric, "set"):
            import typing

            typing.cast("typing.Any", metric).set(value, tags)
        elif hasattr(metric, "record"):
            metric.record(value, tags)

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram value."""
        metric = self._metrics.get(name)
        if metric is None:
            metric = self.create_histogram(name, labels=tags)
        if hasattr(metric, "observe"):
            import typing

            typing.cast("typing.Any", metric).observe(value, tags)
        elif hasattr(metric, "record"):
            metric.record(value, tags)
