"""Worker lifecycle dataclasses.

Extracted from ``quadkit.tasks.execution.worker`` to keep that module
under the 700-line limit.  Contains the dataclasses that represent optional
infrastructure services and per-worker statistics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, Any

from quadkit.logging import LoggerProtocol as Logger

if TYPE_CHECKING:
    from quadkit.contracts.core import HookRegistryProtocol, TaskManagerProtocol
    from quadkit.contracts.infra.resilience import RetryPolicyProtocol
    from quadkit.tasks.dlq.core import DeadLetterQueue
    from quadkit.tasks.observability.core import TaskDashboard
    from quadkit.tasks.progress.core import ProgressStore
    from quadkit.tasks.results.core import ResultStore

from quadkit.tasks.models.job import JobResult

__all__ = ["TaskWorkerServices", "WorkerJobStats"]


@dataclass
class TaskWorkerServices:
    """Optional infrastructure services injected into a :class:`TaskWorker`.

    Groups all optional infrastructure dependencies so that the
    ``TaskWorker`` constructor stays focused on the mandatory parameters.
    All fields default to ``None`` — omitted services degrade gracefully.

    Attributes:
        container: DI container for resolving task dependencies.
        dead_letter_queue: DLQ for routing permanently-failed jobs.
        result_store: Persistent store for job execution results.
        progress_store: Store for in-progress task progress updates.
        dashboard: Observability dashboard for worker and job metrics.
        retry_policy: Retry policy implementation (from ``the optional provider``).
        task_manager: Kernel task manager for critical shutdown registration.
        idempotency_manager: Manager for at-most-once job execution.
        logger: Optional logger instance.
    """

    container: Any = None
    dead_letter_queue: DeadLetterQueue | None = None
    result_store: ResultStore | None = None
    progress_store: ProgressStore | None = None
    dashboard: TaskDashboard | None = None
    retry_policy: RetryPolicyProtocol | None = None
    task_manager: TaskManagerProtocol | None = None
    idempotency_manager: Any | None = None
    logger: Logger | None = None
    hooks: HookRegistryProtocol | None = None


@dataclass
class WorkerJobStats:
    """Worker statistics for monitoring performance.

    Tracks execution metrics for an individual worker including
    job counts, timing, and activity tracking.
    """

    worker_id: str
    jobs_processed: int = 0
    jobs_succeeded: int = 0
    jobs_failed: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    @property
    def uptime(self) -> float:
        """Get worker uptime in seconds."""
        return time.time() - self.started_at

    def record_job(self, result: JobResult) -> None:
        """Record job execution statistics.

        Args:
            result: JobProtocol execution result.
        """
        self.jobs_processed += 1
        self.total_processing_time += result.duration
        self.average_processing_time = self.total_processing_time / self.jobs_processed
        self.last_activity = time.time()

        if result.success:
            self.jobs_succeeded += 1
        else:
            self.jobs_failed += 1
