"""Worker pool and execution management

This module provides worker management for task processing,
including health monitoring and statistics.
"""

from __future__ import annotations

from quadkit.tasks.execution.health import TaskHealth
from quadkit.tasks.execution.metrics import TaskMetricsCollector
from quadkit.tasks.execution.pool import WorkerPool
from quadkit.tasks.execution.registry import HandlerRegistry
from quadkit.tasks.execution.worker import (
    TaskWorker,
    TaskWorkerServices,
    WorkerJobStats,
)

__all__ = [
    "HandlerRegistry",
    # Metrics
    "TaskHealth",
    "TaskMetricsCollector",
    "TaskWorker",
    "TaskWorkerServices",
    "WorkerJobStats",
    "WorkerPool",
]
