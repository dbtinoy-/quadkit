"""Cardinality validation for Prometheus metrics.

Prevents unbounded label cardinality that can cause OOM in Prometheus.
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock

DEFAULT_MAX_CARDINALITY = 100
OVERFLOW_LABEL_VALUE = "__overflow__"


class CardinalityValidator:
    """Normalizes metric labels to prevent unbounded cardinality growth.

    Prometheus metrics with high-cardinality labels (e.g., user IDs, session IDs)
    can cause memory exhaustion. This validator tracks unique label values per
    metric and collapses excess values into a sentinel bucket.

    Example:
        ```python
        validator = CardinalityValidator(max_cardinality=100)
        labels = {"user_id": "12345"}
        validator.validate_labels("user_login", labels)
        # labels is normalized in place and also returned
        emit_metric(labels=labels)
        # After 100 unique user_ids, new values become "__overflow__"
        ```
    """

    def __init__(
        self,
        max_cardinality: int = DEFAULT_MAX_CARDINALITY,
    ) -> None:
        """Initialize the cardinality validator.

        Args:
            max_cardinality: Maximum unique label values allowed per metric.
                           Defaults to 100.
        """
        self._max_cardinality = max_cardinality
        self._label_values: dict[str, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        self._label_combinations: dict[str, set[tuple[tuple[str, str], ...]]] = (
            defaultdict(set)
        )
        self._lock = Lock()

    def validate_labels(
        self,
        name: str,
        labels: dict[str, str],
    ) -> dict[str, str]:
        """Normalize labels so cardinality stays bounded.

        Args:
            name: MetricProtocol name.
            labels: Label key-value pairs.

        Returns:
            The same labels mapping after in-place normalization to include
            the overflow sentinel for values beyond the configured cardinality
            limit.
        """
        if not labels:
            return labels

        normalized_labels = labels

        with self._lock:
            metric_combinations = self._label_combinations[name]
            combination = tuple(sorted(labels.items()))

            if combination not in metric_combinations:
                if len(metric_combinations) < self._max_cardinality:
                    metric_combinations.add(combination)
                else:
                    normalized_labels = dict.fromkeys(labels, OVERFLOW_LABEL_VALUE)
                    labels.clear()
                    labels.update(normalized_labels)
                    overflow_combination = tuple(sorted(labels.items()))
                    metric_combinations.add(overflow_combination)
                    normalized_labels = labels

            metric_labels = self._label_values[name]
            for label_key, label_value in normalized_labels.items():
                metric_labels[label_key].add(label_value)

        return normalized_labels

    def get_cardinality(self, name: str, label_key: str) -> int:
        """Get the current cardinality for a metric label.

        Args:
            name: MetricProtocol name.
            label_key: Label key.

        Returns:
            Number of unique values for the label.
        """
        with self._lock:
            return len(self._label_values[name].get(label_key, set()))

    def reset(self, name: str | None = None) -> None:
        """Reset cardinality tracking.

        Args:
            name: If provided, reset only this metric. Otherwise reset all.
        """
        with self._lock:
            if name is None:
                self._label_values.clear()
                self._label_combinations.clear()
            else:
                self._label_values.pop(name, None)
                self._label_combinations.pop(name, None)

    def set_max_cardinality(self, max_cardinality: int) -> None:
        """Update the maximum cardinality threshold.

        Args:
            max_cardinality: New maximum unique label values allowed.
        """
        self._max_cardinality = max_cardinality


__all__ = [
    "DEFAULT_MAX_CARDINALITY",
    "OVERFLOW_LABEL_VALUE",
    "CardinalityValidator",
]
