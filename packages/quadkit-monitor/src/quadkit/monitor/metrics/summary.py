from __future__ import annotations

from collections import deque
import time

from quadkit.contracts.observability.metrics import MetricProtocol
from quadkit.monitor.metrics.series import SeriesKey, series_key
from quadkit.monitor.types import MetricValue

MAX_METRIC_VALUES = 10_000


class Summary(MetricProtocol):
    """Summary metric for calculating quantiles."""

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ):
        self._name = name
        self._description = description
        self.labels = labels or {}
        self._values: deque[MetricValue] = deque(maxlen=MAX_METRIC_VALUES)
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

    def get_series_observations(self) -> dict[SeriesKey, list[float]]:
        """Return the observations recorded for every label set.

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
