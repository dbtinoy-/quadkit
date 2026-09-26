"""Worker pool management

This module provides WorkerPool for managing multiple workers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import LoggerProtocol as Logger

try:
    import psutil  # type: ignore[import-untyped]

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None

from quadkit.concurrency.executors.parallel import Parallel
from quadkit.contracts.core import (
    ExecutionStrategy,
    TaskManagerProtocol,
)
from quadkit.logging import get_logger
from quadkit.tasks.dlq.core import DeadLetterQueue
from quadkit.tasks.execution.registry import HandlerRegistry
from quadkit.tasks.execution.worker import (
    TaskWorker,
    TaskWorkerServices,
    WorkerJobStats,
)
from quadkit.tasks.middleware.core import TaskMiddlewarePipeline

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core import HookRegistryProtocol
    from quadkit.contracts.infra.tasks import TaskQueueProtocol
    from quadkit.tasks.results.core import ResultStore

_logger = get_logger(__name__)


class WorkerPool:
    """Pool of task workers with monitoring and scaling

    WorkerPool manages multiple TaskWorker instances for concurrent
    job processing. Supports dynamic scaling and aggregate statistics.

    Example:
        ```python
        pool = WorkerPool(queue, handlers, size=4)
        await pool.start()
        stats = pool.get_pool_stats()
        await pool.scale_to(8)  # Scale up
        await pool.stop()
        ```
    """

    def __init__(
        self,
        queue: TaskQueueProtocol,
        handler_registry: dict[str, Callable[..., Any]] | HandlerRegistry,
        size: int = 1,
        logger: Logger | None = None,
        task_manager: TaskManagerProtocol | None = None,
        dead_letter_queue: DeadLetterQueue | None = None,
        hooks: HookRegistryProtocol | None = None,
        container: Any = None,
        middleware_pipeline: TaskMiddlewarePipeline | None = None,
    ):
        """Initialize worker pool

        Args:
            queue: TaskQueueProtocol for workers to pull from
            handler_registry: Dict mapping job names to handlers, or HandlerRegistry
                for refreshable lookups after late registrations.
            size: Number of workers to create
            task_manager: Optional kernel task manager for critical task
                registration during worker lifecycle.
            dead_letter_queue: Optional shared DLQ for permanently failed jobs.
            container: Optional DI container for resolving task dependencies at runtime.
            middleware_pipeline: Optional middleware pipeline applied to every
                worker created by this pool.
        """
        self.queue = queue
        self._handler_registry = handler_registry
        self.handlers = (
            handler_registry.to_dict()
            if isinstance(handler_registry, HandlerRegistry)
            else handler_registry
        )
        self.size = size
        self.workers: list[TaskWorker] = []
        self.running = False
        self._task_manager = task_manager
        self._dead_letter_queue = dead_letter_queue or DeadLetterQueue()
        self._hooks = hooks
        self._container = container
        self._middleware_pipeline = middleware_pipeline
        self._result_store: ResultStore | None = None

        # Initialize logger
        if logger is None:
            logger = get_logger(__name__)
        self.logger = logger.bind(pool_size=size)

    def refresh_handlers(self) -> dict[str, Callable[..., Any]]:
        """Refresh handlers from registry if using dynamic registry."""
        if isinstance(self._handler_registry, HandlerRegistry):
            self.handlers = self._handler_registry.to_dict()
            for worker in self.workers:
                worker.handlers = self.handlers
        return self.handlers

    def _create_worker(
        self,
        worker_id: str,
        result_store: ResultStore | None = None,
    ) -> TaskWorker:
        """Create a worker with the pool's shared infrastructure services."""
        return TaskWorker(
            worker_id,
            self.queue,
            self.handlers,
            services=TaskWorkerServices(
                container=self._container,
                dead_letter_queue=self._dead_letter_queue,
                result_store=result_store,
                logger=self.logger,
                task_manager=self._task_manager,
                hooks=self._hooks,
            ),
            middleware_pipeline=self._middleware_pipeline,
        )

    async def _resolve_result_store(self) -> ResultStore | None:
        """Resolve the container-managed result store, when available."""
        if self._container is None:
            return None
        try:
            from quadkit.tasks.results.core import ResultStore

            store: ResultStore | None = await self._container.resolve(ResultStore)
            return store
        except Exception:  # noqa: BLE001 - resolution failure means no store
            return None

    async def start(self) -> None:
        """Start the worker pool

        Creates and starts all workers in the pool.
        """
        self.running = True
        result_store = await self._resolve_result_store()
        self._result_store = result_store

        # Create workers
        for i in range(self.size):
            worker_id = f"worker-{i + 1}"
            worker = self._create_worker(worker_id, result_store=self._result_store)
            self.workers.append(worker)

        # Start all workers concurrently
        start_tasks = [worker.start() for worker in self.workers]
        await Parallel.execute(*start_tasks, strategy=ExecutionStrategy.ALL_SETTLED)

        self.logger.info("Worker pool started with %d workers", self.size)

    async def stop(
        self,
        drain: bool = False,
        timeout: float | None = 30.0,
    ) -> None:
        """Stop the worker pool gracefully.

        Args:
            drain: If ``True``, wait for each worker to finish its current
                job before stopping.  Defaults to ``False`` for a fast
                cancel-and-stop.
            timeout: Per-worker seconds to wait when *drain* is ``True``.
                ``None`` means wait indefinitely.  Defaults to 30 seconds.
        """
        self.running = False

        # Stop all workers concurrently, propagating drain / timeout
        stop_tasks = [
            worker.stop(drain=drain, timeout=timeout) for worker in self.workers
        ]
        await Parallel.execute(*stop_tasks, strategy=ExecutionStrategy.ALL_SETTLED)

        self.logger.info("Worker pool stopped")

    def get_worker_stats(self) -> list[WorkerJobStats]:
        """Get statistics for all workers

        Returns:
            List of WorkerJobStats for each worker
        """
        return [worker.get_stats() for worker in self.workers]

    def get_pool_stats(self) -> dict[str, Any]:
        """Get aggregate pool statistics

        Returns:
            Dictionary with pool-wide statistics
        """
        worker_stats = self.get_worker_stats()

        stats = {
            "pool_size": self.size,
            "active_workers": len(list(filter(lambda w: w.is_busy(), self.workers))),
            "total_jobs_processed": sum(s.jobs_processed for s in worker_stats),
            "total_jobs_succeeded": sum(s.jobs_succeeded for s in worker_stats),
            "total_jobs_failed": sum(s.jobs_failed for s in worker_stats),
            "average_processing_time": (
                sum(s.average_processing_time for s in worker_stats) / len(worker_stats)
                if worker_stats
                else 0
            ),
        }

        # Add system metrics if psutil available
        if HAS_PSUTIL:
            stats["system_cpu_percent"] = psutil.cpu_percent()
            stats["system_memory_percent"] = psutil.virtual_memory().percent

        return stats

    async def scale_to(self, new_size: int) -> None:
        """Scale the worker pool to a new size

        Dynamically add or remove workers.

        Args:
            new_size: Target number of workers
        """
        if new_size == self.size:
            return

        if new_size > self.size:
            # Add workers
            for i in range(self.size, new_size):
                worker_id = f"worker-{i + 1}"
                worker = self._create_worker(worker_id, result_store=self._result_store)
                self.workers.append(worker)
                await worker.start()
                self.logger.info("Added %s", worker_id)
        else:
            # Remove workers
            workers_to_remove = self.workers[new_size:]
            self.workers = self.workers[:new_size]

            stop_tasks = [worker.stop() for worker in workers_to_remove]
            await Parallel.execute(*stop_tasks, strategy=ExecutionStrategy.ALL_SETTLED)
            self.logger.info("Removed %d workers", len(workers_to_remove))

        self.size = new_size
        self.logger.info("Worker pool scaled to %d workers", new_size)
