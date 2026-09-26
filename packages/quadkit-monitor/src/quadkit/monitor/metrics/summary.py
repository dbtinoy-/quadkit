from __future__ import annotations

from collections import deque
import time

from quadkit.contracts.observability.metrics import MetricProtocol
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

    def observe(
        self,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Alias for :meth:`record` — delegates to the canonical implementation."""
        self.record(value, labels)

    def get_observations(self) -> list[float]:
        return list(self._observations)

    def reset(self) -> None:
        """Clear all observations and values for metric rotation."""
        self._observations.clear()
        self._values.clear()
