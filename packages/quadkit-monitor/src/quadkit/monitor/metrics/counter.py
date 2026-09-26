from __future__ import annotations

from collections import deque
import time

from quadkit.contracts.observability.metrics import MetricProtocol
from quadkit.monitor.types import MetricValue

MAX_METRIC_VALUES = 10_000


class Counter(MetricProtocol):
    """Monotonically increasing counter."""

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
        self._count = 0

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
        self._count += int(value)
        self._values.append(
            MetricValue(self.name, self._count, combined_labels, time.time()),
        )

    def increment(
        self,
        amount: int = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Alias for :meth:`record` — delegates to the canonical implementation."""
        self.record(float(amount), labels)

    def get_count(self) -> int:
        return self._count

    def reset(self) -> None:
        """Reset the counter to zero and clear the observation history."""
        self._count = 0
        self._values.clear()
