"""Metrics configuration."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.config import BaseConfig
from quadkit.monitor import constants as monitor_const
from quadkit.validation import Field


@dataclass(init=False)
class MetricsConfig(BaseConfig):
    """Configuration for metrics collection.

    Attributes:
        enabled: Whether metrics collection is enabled.
        prefix: Prefix for all metric names.
        default_labels: Default labels to add to all metrics.
        histogram_buckets: Default bucket boundaries for histograms.
        collection_interval: Interval for periodic metrics collection (seconds).
    """

    enabled: bool = Field(True, description="Enable metrics collection")
    prefix: str = Field(
        monitor_const.METRIC_PREFIX, description="MetricProtocol name prefix"
    )
    default_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Default labels for all metrics",
    )
    histogram_buckets: list[float] = Field(
        default_factory=lambda: list(monitor_const.DEFAULT_DURATION_BUCKETS),
        description="Default histogram bucket boundaries",
    )
    collection_interval: float = Field(
        60.0,
        ge=1.0,
        description="Metrics collection interval in seconds",
    )

    def make_metric_name(self, name: str) -> str:
        """Create a prefixed metric name.

        Args:
            name: The metric name.

        Returns:
            Prefixed metric name.
        """
        if self.prefix:
            return f"{self.prefix}_{name}"
        return name


__all__ = [
    "MetricsConfig",
]
