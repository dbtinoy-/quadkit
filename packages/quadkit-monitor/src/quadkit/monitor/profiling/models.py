from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Any

from quadkit.domain import DomainModel
from quadkit.monitor.exceptions import MonitorError
from quadkit.validation import Field


class PerformanceMonitorError(MonitorError):
    """Base exception for performance monitoring errors."""

    _code = "QK_ERR_MONITOR_008"

    def __init__(
        self, message: str = "Performance monitoring error", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


@dataclass(init=False)
class PerformanceMonitorConfig(DomainModel):
    """Configuration for performance monitoring."""

    enable_memory_tracking: bool = Field(default=True)
    enable_cpu_profiling: bool = Field(default=False)
    sampling_interval: float = Field(default=1.0, gt=0)
    max_metrics_history: int = Field(default=1000, gt=0)
    profile_sort_by: str = Field(default="cumulative")
    profile_max_lines: int = Field(default=50, gt=0)


@dataclass
class PerformanceSnapshot:
    """A single performance metrics snapshot."""

    timestamp: float
    cpu_percent: float
    memory_usage: int
    memory_peak: int
    active_tasks: int
    pending_tasks: int
    total_tasks: int
    memory_traces: list[str] | None = None


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""

    snapshots: deque[PerformanceSnapshot] = field(
        default_factory=lambda: deque(maxlen=1000)
    )
    start_time: float | None = None
    end_time: float | None = None
    total_samples: int = 0
    average_cpu_percent: float = 0.0
    average_memory_usage: float = 0.0
    peak_memory_usage: int = 0
    max_active_tasks: int = 0
    profile_data: str | None = None

    @property
    def duration(self) -> float | None:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        if self.start_time:
            return time.monotonic() - self.start_time
        return None

    @property
    def samples_per_second(self) -> float:
        duration = self.duration
        if duration and duration > 0:
            return self.total_samples / duration
        return 0.0


@dataclass
class FunctionProfileResult:
    """Result of profiling a function."""

    function_name: str
    execution_time: float
    cpu_time: float
    memory_delta: int
    profile_stats: str | None = None
    memory_traces: list[str] | None = None
