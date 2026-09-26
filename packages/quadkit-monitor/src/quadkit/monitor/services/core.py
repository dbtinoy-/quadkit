"""Unified observability service for traces, metrics, and health.

Provides a single entry point for observability that works with or without
the ``quadkit-monitor`` extension. Falls back to NoOp implementations
when the full monitoring stack is not available.

Example::

    from quadkit.observability.di import ObservabilityService

    obs = ObservabilityService()
    with obs.trace("process_order", order_id=order_id) as span:
        span.set_attribute("amount", 99.99)
        ...
    obs.counter("orders_processed").increment()
"""

from __future__ import annotations

from contextlib import contextmanager
import time
from typing import TYPE_CHECKING, Any

from quadkit.observability.core import (
    NoOpMetricsCollector,
    NoOpTracer,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from quadkit.contracts.observability.metrics import (
        MetricProtocol,
        MetricsCollectorProtocol,
    )
    from quadkit.contracts.observability.tracing import SpanProtocol, TracerProtocol


class MetricProxy:
    """Proxy for a specific metric that provides a stateful API.

    Bridges the gap between the ``MetricsCollectorProtocol`` (which is name-based)
    and consumers who expect a persistent metric object.
    """

    __slots__ = ("_collector", "_metrics_type", "_name", "_value", "_values")

    def __init__(
        self, name: str, collector: MetricsCollectorProtocol, metrics_type: str
    ) -> None:
        self._name = name
        self._collector = collector
        self._metrics_type = metrics_type
        # State tracking for backward compatibility with NoOp tests
        self._value = 0.0
        self._values: list[float] = []

    @property
    def name(self) -> str:
        """MetricProtocol name."""
        return self._name

    def increment(self, amount: float = 1.0) -> None:
        """Increment the counter."""
        self._collector.increment(self._name, amount)
        self._value += amount

    def record(self, value: float) -> None:
        """Record a histogram value."""
        self._collector.histogram(self._name, value)
        self._values.append(value)

    @property
    def value(self) -> float:
        """Current counter value (tracked locally)."""
        return self._value


class ObservabilityService:
    """Unified service for observability (traces, metrics, health).

    Automatically detects if the ``quadkit-monitor`` extension is
    available and delegates to it. Otherwise, uses NoOp implementations
    that still allow application code to instrument without errors.

    Args:
        tracer: Optional tracer backend. If ``None``, uses :class:`NoOpTracer`.
        meter: Optional meter backend. If ``None``, uses :class:`NoOpMetricsCollector`.
    """

    __slots__ = ("_counters", "_histograms", "_meter", "_tracer")

    def __init__(
        self,
        tracer: TracerProtocol | None = None,
        meter: MetricsCollectorProtocol | None = None,
    ) -> None:
        self._tracer = tracer or NoOpTracer()
        self._meter = meter or NoOpMetricsCollector()
        self._counters: dict[str, MetricProxy] = {}
        self._histograms: dict[str, MetricProxy] = {}

    def register_metric(self, metric: MetricProtocol) -> None:
        """Register an existing metric instrument.

        Args:
            metric: Pre-defined metric instance.
        """
        self._meter.register_metric(metric)

    @contextmanager
    def trace(self, name: str, **attributes: Any) -> Iterator[SpanProtocol]:
        """Create a tracing span.

        If a real tracer is configured, delegates to its ``start_span``
        method. Otherwise yields a ``NoOpSpan``.

        Args:
            name: Span name.
            **attributes: Initial span attributes.

        Yields:
            A span object with ``set_attribute()`` and ``add_event()`` methods.
        """
        span = self._tracer.start_span(name, attributes=attributes or None)
        try:
            yield span
        except (
            Exception
        ) as exc:  # context manager must capture all exceptions for tracing
            span.record_exception(exc)
            raise
        finally:
            if hasattr(span, "end"):
                span.end()

    def counter(self, name: str) -> MetricProxy:
        """Get or create a counter metric.

        Args:
            name: Counter name.

        Returns:
            A counter with ``increment()`` method.
        """
        if name not in self._counters:
            self._counters[name] = MetricProxy(name, self._meter, "counter")
        return self._counters[name]

    def histogram(self, name: str) -> MetricProxy:
        """Get or create a histogram metric.

        Args:
            name: Histogram name.

        Returns:
            A histogram with ``record()`` method.
        """
        if name not in self._histograms:
            self._histograms[name] = MetricProxy(name, self._meter, "histogram")
        return self._histograms[name]

    @contextmanager
    def timed(self, metric_name: str) -> Iterator[None]:
        """Context manager that records execution duration as a histogram.

        Args:
            metric_name: The histogram metric name.

        Yields:
            None — timing is recorded on exit.
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.histogram(metric_name).record(elapsed)


__all__ = [
    "MetricProxy",
    "ObservabilityService",
]
