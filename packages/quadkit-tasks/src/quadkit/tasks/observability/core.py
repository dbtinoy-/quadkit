"""Enhanced observability for task execution.

Dashboard-ready metrics: throughput, latency percentiles,
queue depth, error rate, and execution history.

Example:
    dashboard = TaskDashboard()
    dashboard.record_execution("send_email", duration_ms=150, success=True)
    dashboard.record_execution("process_order", duration_ms=1200, success=False)

    stats = dashboard.get_summary()
    history = dashboard.get_recent_executions(limit=20)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import time
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionRecord:
    """Record of a single task execution."""

    job_id: str
    task_name: str
    success: bool
    duration_ms: float
    error: str | None = None
    timestamp: float = field(default_factory=time.time)
    worker_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the execution record to a plain dictionary."""
        return {
            "job_id": self.job_id,
            "task_name": self.task_name,
            "success": self.success,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
            "timestamp": self.timestamp,
            "worker_id": self.worker_id,
        }


class TaskDashboard:
    """Aggregated task observability dashboard."""

    def __init__(
        self,
        *,
        history_size: int = 1000,
        window_seconds: float = 300,
    ) -> None:
        self._history: deque[ExecutionRecord] = deque(maxlen=history_size)
        self._window_seconds = window_seconds

        # Per-task-type counters
        self._task_counts: dict[str, int] = {}
        self._task_failures: dict[str, int] = {}
        self._task_durations: dict[str, list[float]] = {}

        # Global counters
        self._total_executed = 0
        self._total_failed = 0
        self._started_at = time.time()

    def record_execution(
        self,
        task_name: str,
        *,
        job_id: str = "",
        duration_ms: float = 0.0,
        success: bool = True,
        error: str | None = None,
        worker_id: str | None = None,
    ) -> None:
        """Record a task execution."""
        record = ExecutionRecord(
            job_id=job_id,
            task_name=task_name,
            success=success,
            duration_ms=duration_ms,
            error=error,
            worker_id=worker_id,
        )
        self._history.append(record)

        # Update counters
        self._total_executed += 1
        self._task_counts[task_name] = self._task_counts.get(task_name, 0) + 1

        if not success:
            self._total_failed += 1
            self._task_failures[task_name] = self._task_failures.get(task_name, 0) + 1

        # Track durations (keep last 100 per task type)
        if task_name not in self._task_durations:
            self._task_durations[task_name] = []
        durations = self._task_durations[task_name]
        durations.append(duration_ms)
        if len(durations) > 100:
            self._task_durations[task_name] = durations[-100:]

    def get_summary(self) -> dict[str, Any]:
        """Get dashboard summary with throughput and error rates."""
        uptime = time.time() - self._started_at
        throughput = self._total_executed / uptime if uptime > 0 else 0

        # Window-based throughput (last N seconds)
        cutoff = time.time() - self._window_seconds
        recent = [r for r in self._history if r.timestamp > cutoff]
        window_throughput = (
            len(recent) / self._window_seconds if self._window_seconds > 0 else 0
        )

        error_rate = (
            self._total_failed / self._total_executed * 100
            if self._total_executed > 0
            else 0
        )

        return {
            "total_executed": self._total_executed,
            "total_failed": self._total_failed,
            "error_rate_pct": round(error_rate, 2),
            "throughput_per_sec": round(throughput, 2),
            "window_throughput_per_sec": round(window_throughput, 2),
            "uptime_seconds": round(uptime, 1),
            "task_types": len(self._task_counts),
        }

    def get_per_task_stats(self) -> dict[str, dict[str, Any]]:
        """Get per-task-type statistics with latency percentiles."""
        stats: dict[str, dict[str, Any]] = {}

        for name, count in self._task_counts.items():
            durations = self._task_durations.get(name, [])
            failures = self._task_failures.get(name, 0)

            stat: dict[str, Any] = {
                "count": count,
                "failures": failures,
                "error_rate_pct": round(
                    failures / count * 100 if count > 0 else 0,
                    2,
                ),
            }

            if durations:
                sorted_d = sorted(durations)
                stat["latency"] = {
                    "avg_ms": round(sum(sorted_d) / len(sorted_d), 2),
                    "min_ms": round(sorted_d[0], 2),
                    "max_ms": round(sorted_d[-1], 2),
                    "p50_ms": round(
                        _percentile(sorted_d, 50),
                        2,
                    ),
                    "p95_ms": round(
                        _percentile(sorted_d, 95),
                        2,
                    ),
                    "p99_ms": round(
                        _percentile(sorted_d, 99),
                        2,
                    ),
                }

            stats[name] = stat

        return stats

    def get_recent_executions(
        self,
        *,
        limit: int = 50,
        task_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent execution history."""
        records = list(reversed(self._history))
        if task_name:
            records = [r for r in records if r.task_name == task_name]
        return [r.to_dict() for r in records[:limit]]

    def get_error_breakdown(self) -> dict[str, list[dict[str, Any]]]:
        """Get recent errors grouped by task type."""
        errors: dict[str, list[dict[str, Any]]] = {}
        for record in reversed(self._history):
            if not record.success and record.error:
                if record.task_name not in errors:
                    errors[record.task_name] = []
                if len(errors[record.task_name]) < 5:
                    errors[record.task_name].append(
                        {
                            "job_id": record.job_id,
                            "error": record.error,
                            "timestamp": record.timestamp,
                        }
                    )
        return errors

    def reset(self) -> None:
        """Reset all counters and history."""
        self._history.clear()
        self._task_counts.clear()
        self._task_failures.clear()
        self._task_durations.clear()
        self._total_executed = 0
        self._total_failed = 0
        self._started_at = time.time()


def _percentile(sorted_data: list[float], pct: float) -> float:
    """Calculate percentile from sorted data."""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * (pct / 100)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1
