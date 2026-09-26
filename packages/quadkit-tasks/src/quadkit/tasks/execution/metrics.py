"""Enhanced dispatcher metrics collection for observability.

This module provides optional metrics collection for task execution,
queue monitoring, and executor utilization tracking.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from quadkit.contracts.observability.metrics import MetricsRecorderProtocol


@dataclass
class TaskMetrics:
    """Metrics for a single task execution."""

    """Metrics for a single task execution."""

    task_id: str
    func_name: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float | None = None
    success: bool = True
    error: str | None = None
    executor_type: str = "async"  # "async", "cpu_pool", "io_pool"


@dataclass
class ExecutorMetrics:
    """Metrics for thread pool executor utilization."""

    executor_name: str
    max_workers: int
    active_workers: int = 0
    queued_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_execution_time_ms: float = 0.0

    def avg_execution_time_ms(self) -> float:
        """Calculate average execution time."""
        if self.completed_tasks == 0:
            return 0.0
        return self.total_execution_time_ms / self.completed_tasks

    def utilization_percent(self) -> float:
        """Calculate executor utilization percentage."""
        if self.max_workers == 0:
            return 0.0
        return (self.active_workers / self.max_workers) * 100.0


class TaskMetricsCollector:
    """Collects and aggregates dispatcher metrics.

    This is an optional component that can be enabled for observability.
    When disabled, it has zero overhead.
    """

    def __init__(
        self,
        enabled: bool = False,
        max_history: int = 1000,
        track_individual_tasks: bool = True,
        metrics_recorder: MetricsRecorderProtocol | None = None,
    ) -> None:
        """Initialize metrics collector.

        Args:
            enabled: Whether to collect metrics
            max_history: Maximum number of task records to keep
            track_individual_tasks: Whether to track individual task executions
            metrics_recorder: Optional kernel metrics recorder to forward
                aggregated counters and histograms to.

        """
        self.enabled = enabled
        self.max_history = max_history
        self.track_individual_tasks = track_individual_tasks
        self._metrics_recorder = metrics_recorder

        self._lock = asyncio.Lock()
        self._task_history: deque[TaskMetrics] = deque(maxlen=max_history)
        self._executor_metrics: dict[str, ExecutorMetrics] = {}

        # Aggregate counters
        self._total_tasks = 0
        self._successful_tasks = 0
        self._failed_tasks = 0
        self._total_execution_time_ms = 0.0

    async def record_task_start(
        self,
        task_id: str,
        func_name: str,
        executor_type: str = "async",
    ) -> TaskMetrics | None:
        """Record the start of a task execution.

        Args:
            task_id: Unique task identifier
            func_name: Name of the function being executed
            executor_type: Type of executor ("async", "cpu_pool", "io_pool")

        Returns:
            TaskMetrics object if enabled, None otherwise

        """
        if not self.enabled:
            return None

        metrics = TaskMetrics(
            task_id=task_id,
            func_name=func_name,
            started_at=datetime.now(UTC),
            executor_type=executor_type,
        )

        async with self._lock:
            self._total_tasks += 1

            # Update executor metrics
            if executor_type in self._executor_metrics:
                self._executor_metrics[executor_type].active_workers += 1

        if self._metrics_recorder is not None:
            self._metrics_recorder.increment(
                "tasks.started",
                tags={"func": func_name, "executor": executor_type},
            )

        return metrics

    async def record_task_complete(
        self,
        metrics: TaskMetrics | None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Record task completion.

        Args:
            metrics: TaskMetrics object from record_task_start
            success: Whether the task completed successfully
            error: Error message if task failed

        """
        if not self.enabled or metrics is None:
            return

        metrics.completed_at = datetime.now(UTC)
        metrics.success = success
        metrics.error = error

        # Calculate duration
        duration = (metrics.completed_at - metrics.started_at).total_seconds() * 1000
        metrics.duration_ms = duration

        async with self._lock:
            if success:
                self._successful_tasks += 1
            else:
                self._failed_tasks += 1

            self._total_execution_time_ms += duration

            # Update executor metrics
            executor_type = metrics.executor_type
            if executor_type in self._executor_metrics:
                exec_metrics = self._executor_metrics[executor_type]
                exec_metrics.active_workers = max(0, exec_metrics.active_workers - 1)
                exec_metrics.completed_tasks += 1
                exec_metrics.total_execution_time_ms += duration

                if not success:
                    exec_metrics.failed_tasks += 1

            # Store task history if tracking individual tasks
            if self.track_individual_tasks:
                self._task_history.append(metrics)

        if self._metrics_recorder is not None:
            executor_type = metrics.executor_type
            if success:
                self._metrics_recorder.increment(
                    "tasks.completed",
                    tags={"func": metrics.func_name, "executor": executor_type},
                )
            else:
                self._metrics_recorder.increment(
                    "tasks.failed",
                    tags={"func": metrics.func_name, "executor": executor_type},
                )
            if metrics.duration_ms is not None:
                self._metrics_recorder.histogram(
                    "tasks.duration_ms",
                    metrics.duration_ms,
                    tags={"func": metrics.func_name, "executor": executor_type},
                )

    async def register_executor(self, executor_name: str, max_workers: int) -> None:
        """Register an executor for metrics tracking.

        Args:
            executor_name: Name of the executor
            max_workers: Maximum number of workers

        """
        if not self.enabled:
            return

        async with self._lock:
            self._executor_metrics[executor_name] = ExecutorMetrics(
                executor_name=executor_name,
                max_workers=max_workers,
            )

    async def get_summary(self) -> dict[str, Any]:
        """Get summary of all metrics.

        Returns:
            Dictionary containing aggregated metrics

        """
        if not self.enabled:
            return {"enabled": False}

        async with self._lock:
            avg_execution_time = (
                self._total_execution_time_ms / self._total_tasks
                if self._total_tasks > 0
                else 0.0
            )

            success_rate = (
                (self._successful_tasks / self._total_tasks) * 100
                if self._total_tasks > 0
                else 0.0
            )

            return {
                "enabled": True,
                "total_tasks": self._total_tasks,
                "successful_tasks": self._successful_tasks,
                "failed_tasks": self._failed_tasks,
                "success_rate_percent": success_rate,
                "avg_execution_time_ms": avg_execution_time,
                "total_execution_time_ms": self._total_execution_time_ms,
                "executor_metrics": {
                    name: {
                        "max_workers": metrics.max_workers,
                        "active_workers": metrics.active_workers,
                        "queued_tasks": metrics.queued_tasks,
                        "completed_tasks": metrics.completed_tasks,
                        "failed_tasks": metrics.failed_tasks,
                        "utilization_percent": metrics.utilization_percent(),
                        "avg_execution_time_ms": metrics.avg_execution_time_ms(),
                    }
                    for name, metrics in self._executor_metrics.items()
                },
            }

    async def get_recent_tasks(self, limit: int | None = None) -> list[TaskMetrics]:
        """Get recent task execution history.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of recent TaskMetrics

        """
        if not self.enabled or not self.track_individual_tasks:
            return []

        async with self._lock:
            tasks = list(self._task_history)
            if limit:
                tasks = tasks[-limit:]
            return tasks

    async def reset(self) -> None:
        """Reset all metrics."""
        async with self._lock:
            self._task_history.clear()
            self._executor_metrics.clear()
            self._total_tasks = 0
            self._successful_tasks = 0
            self._failed_tasks = 0
            self._total_execution_time_ms = 0.0
