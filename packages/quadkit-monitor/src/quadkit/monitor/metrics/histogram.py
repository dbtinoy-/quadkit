from __future__ import annotations

from collections import deque
import time

from quadkit.contracts.observability.metrics import MetricProtocol
from quadkit.monitor.metrics.series import SeriesKey, series_key
from quadkit.monitor.types import MetricValue

MAX_METRIC_VALUES = 10_000


class Histogram(MetricProtocol):
    """Histogram for measuring distributions."""

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
        buckets: list[float] | None = None,
    ):
        self._name = name
        self._description = description
        self.labels = labels or {}
        self._values: deque[MetricValue] = deque(maxlen=MAX_METRIC_VALUES)
        self.buckets = buckets or [
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
        ]
        self._observations: deque[float] = deque(maxlen=MAX_METRIC_VALUES)
        self._series_observations: dict[SeriesKey, deque[float]] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def record(
        self,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        combined_labels = {**self.labels, **(labels or {})}
        self._observations.append(float(value))
        self._values.append(
            MetricValue(self.name, float(value), combined_labels, time.time()),
        )
        self._series_observations.setdefault(
            series_key(combined_labels), deque(maxlen=MAX_METRIC_VALUES)
        ).append(float(value))

    def observe(
        self,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Alias for :meth:`record` — delegates to the canonical implementation."""
        self.record(value, labels)

    def get_observations(self) -> list[float]:
        return list(self._observations)

    def get_bucket_counts(self) -> dict[float, int]:
        counts = {}
        for bucket in self.buckets:
            counts[bucket] = sum(1 for obs in self._observations if obs <= bucket)
        return counts

    def get_series_observations(self) -> dict[SeriesKey, list[float]]:
        """Return the observations recorded for every label set.

        A Prometheus histogram is exposed per label set (one set of
        ``_bucket``/``_sum``/``_count`` series each); the flat
        ``_observations`` deque cannot be split that way after the fact, so
        observations are retained per label set here.

        Returns:
            Mapping of canonical label key (sorted ``(name, value)`` pairs)
            to that label set's observations.
        """
        return {key: list(values) for key, values in self._series_observations.items()}

    def reset(self) -> None:
        """Clear all observations and values for metric rotation."""
        self._observations.clear()
        self._values.clear()
        self._series_observations.clear()
