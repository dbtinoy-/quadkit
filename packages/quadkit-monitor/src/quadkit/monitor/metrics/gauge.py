from __future__ import annotations

from collections import deque
import time

from quadkit.contracts.observability.metrics import MetricProtocol
from quadkit.monitor.types import MetricValue

MAX_METRIC_VALUES = 10_000


class Gauge(MetricProtocol):
    """Gauge that can go up and down."""

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
        self._value = 0.0

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
        self._value = float(value)
        self._values.append(
            MetricValue(self.name, self._value, combined_labels, time.time()),
        )

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Alias for :meth:`record` — delegates to the canonical implementation."""
        self.record(value, labels)

    def increment(
        self,
        amount: float = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Alias for :meth:`record` — increments gauge by *amount* via canonical implementation."""
        self.record(self._value + float(amount), labels)

    def decrement(
        self,
        amount: float = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Alias for :meth:`record` — decrements gauge by *amount* via canonical implementation."""
        self.record(self._value - float(amount), labels)

    def get_value(self) -> float:
        return self._value

    def reset(self) -> None:
        """Reset the gauge to zero and clear the observation history."""
        self._value = 0.0
        self._values.clear()
