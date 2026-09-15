"""Fake metrics collector for verifying observability instrumentation in tests."""

from __future__ import annotations

__all__ = ["FakeMetricsCollector"]


class FakeMetricsCollector:
    """Records counter, gauge, and histogram observations for test assertions.

    Example::

        metrics = FakeMetricsCollector()
        metrics.increment("requests.total")
        metrics.assert_counter_incremented("requests.total")
    """

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

    def increment(
        self,
        name: str,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Increment counter *name* by *value*."""
        self._counters[name] = self._counters.get(name, 0.0) + value

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record gauge *name* = *value*."""
        self._gauges[name] = value

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram observation for *name*."""
        self._histograms.setdefault(name, []).append(value)

    def counter(self, name: str) -> float:
        """Return the current value of counter *name* (0 if never incremented)."""
        return self._counters.get(name, 0.0)

    def assert_counter(self, name: str, expected: float) -> None:
        """Assert counter *name* equals *expected*."""
        actual = self._counters.get(name, 0.0)
        if actual != expected:
            msg = f"Counter {name!r}: expected {expected}, got {actual}"
            raise AssertionError(msg)

    def assert_counter_incremented(self, name: str) -> None:
        """Assert counter *name* was incremented at least once."""
        if self._counters.get(name, 0.0) <= 0:
            msg = f"Counter {name!r} was never incremented"
            raise AssertionError(msg)

    def assert_gauge(self, name: str, expected: float) -> None:
        """Assert gauge *name* equals *expected*."""
        actual = self._gauges.get(name)
        if actual != expected:
            msg = f"Gauge {name!r}: expected {expected}, got {actual!r}"
            raise AssertionError(msg)

    def clear(self) -> None:
        """Reset all recorded observations."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
