"""Shared types for monitoring.

This module contains data types used across the monitoring package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Protocol

from quadkit.contracts.core import HealthCheckResult


@dataclass
class MetricValue:
    """Represents a metric measurement."""

    name: str
    value: int | float
    labels: dict[str, str]
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> Any:
        """Initialize timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = time.time()


class PerformanceMonitorState(str, Enum):
    """State of the performance monitor."""

    STOPPED = "stopped"
    MONITORING = "monitoring"
    PAUSED = "paused"


class HealthCheckerProtocol(Protocol):
    """Structural contract for a single health-check component.

    Any object implementing ``check()`` satisfies this protocol, regardless
    of inheritance from any concrete class.
    """

    async def check(self) -> HealthCheckResult:
        """Perform the health check and return a result."""
        ...


__all__ = ["HealthCheckerProtocol", "MetricValue", "PerformanceMonitorState"]
