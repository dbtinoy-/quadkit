"""Worker statistics and task execution

This module provides individual worker implementation for task execution.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result
from quadkit.tasks.config import TaskWorkerConfig

# Import DLQ for failed job management
from quadkit.tasks.exceptions import (
    TaskError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskTimeoutError,
)
from quadkit.tasks.execution._concurrency import WorkerConcurrencyMixin
from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies
from quadkit.tasks.execution._failure_handling import send_to_dlq
from quadkit.tasks.execution._invoke import invoke_handler
from quadkit.tasks.execution._lifecycle import TaskWorkerServices, WorkerJobStats
from quadkit.tasks.execution._middleware_chain import (
    create_default_pipeline,
    execute_handler_through_middleware,
)
from quadkit.tasks.hooks import TaskCompletedHook, TaskFailedHook

# Import middleware pipeline components
from quadkit.tasks.middleware.core import (
    TaskMiddlewarePipeline,
)
from quadkit.tasks.models.job import JobProtocol, JobResult

# Import TaskDashboard for observability
# Import ProgressTracker for task progress
from quadkit.tasks.progress.core import ProgressTracker

# Import ResultStore for job results

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core import HookRegistryProtocol
    from quadkit.contracts.infra.tasks import TaskQueueProtocol


class TaskWorker(WorkerConcurrencyMixin):
    """Individual task worker for job execution

    TaskWorker processes jobs from a queue using registered handlers.
    Each worker runs independently and tracks its own statistics.

    Example:
        ```python
        worker = TaskWorker("worker-1", queue, handlers)
        await worker.start()
        # ... worker processes jobs ...
        await worker.stop()
        ```
    """

    def __init__(
        self,
        worker_id: str,
        queue: TaskQueueProtocol,
        handler_registry: dict[str, Callable[..., Any]],
        config: TaskWorkerConfig | None = None,
        services: TaskWorkerServices | None = None,
        *,
        middleware_pipeline: TaskMiddlewarePipeline | None = None,
    ):
        """Initialize task worker.

        Args:
            worker_id: Unique worker identifier.
            queue: TaskQueueProtocol to pull jobs from.
            handler_registry: Dict mapping job names to handler functions.
            config: Optional worker configuration controlling timeouts and execution
                behaviour. Defaults to TaskWorkerConfig() when not provided.
            services: Optional bundle of infrastructure services (DLQ, result
                store, progress store, dashboard, retry policy, task manager,
                idempotency manager, logger). Use :class:`TaskWorkerServices` to
                compose only the services you need; absent services degrade
                gracefully.  Pass a ``logger`` via ``services.logger`` to inject a
                custom bound logger; otherwise a module logger is created and bound
                to ``worker_id`` automatically.
            middleware_pipeline: Optional middleware pipeline for cross-cutting
                concerns.
        """
        _svc = services or TaskWorkerServices()

        self.worker_id = worker_id
        self.queue = queue
        self.handlers = handler_registry
        self.config = config or TaskWorkerConfig()
        self._services = _svc  # Store services reference for DI resolution
        self.idempotency_manager = _svc.idempotency_manager
        self.stats = WorkerJobStats(worker_id=worker_id)
        self.running = False
        self._draining = False  # Graceful drain mode flag
        self.current_job: JobProtocol | None = None
        self._task: asyncio.Task[Any] | None = None

        # Initialize middleware pipeline
        self._middleware = middleware_pipeline or create_default_pipeline(self.config)

        self.dlq = _svc.dead_letter_queue
        self.result_store = _svc.result_store
        self.progress_store = _svc.progress_store
        self.dashboard = _svc.dashboard
        self._task_manager = _svc.task_manager
        self._retry_policy = _svc.retry_policy

        _log = _svc.logger if _svc.logger is not None else get_logger(__name__)
        self.logger = _log.bind(worker_id=worker_id)
        self._hooks: HookRegistryProtocol | None = _svc.hooks

        # Track background tasks
        self._background_tasks: set[asyncio.Task[Any]] = set()

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit a task action hook when a registry is available."""
        if self._hooks is None:
            return

        await self._hooks.call_action(hook_name, payload=payload)

    @staticmethod
    def _stamp_result(job_result: JobResult, job: JobProtocol) -> None:
        """Attach job metadata to a result before it is persisted."""
        job_result.id = job.id
        job_result.name = job.name
        job_result.completed_at = time.time()

    async def _execute_job(self, job: JobProtocol) -> Result[JobResult, TaskError]:
        """Execute a single job with optional retry via injected policy.

        When a ``RetryPolicyProtocol`` was injected at construction the job is
        executed through the policy (exponential back-off, jitter, etc.).
        When no policy is present the job is executed exactly once (fail-open).

        Args:
            job: JobProtocol to execute

        Returns:
            Ok(JobResult) on success; Err(TaskError) on failure (after DLQ routing
            and stats recording have been performed as side-effects).
        """
        self.current_job = job
        start_time = time.time()

        try:
            # Check idempotency - skip if already completed
            if job.idempotency_key and self.idempotency_manager:
                existing = await self.idempotency_manager.check_duplicate(
                    job.idempotency_key,
                )
                if existing and existing.status == "completed":
                    self.logger.info(
                        "Worker %s skipping job %s - already completed (idempotency_key=%s)",
                        self.worker_id,
                        job.id,
                        job.idempotency_key,
                    )
                    duration = time.time() - start_time
                    job_result = JobResult.ok(existing.result, duration)
                    job.mark_completed(job_result)
                    self.stats.record_job(job_result)
                    return Ok(job_result)

            job.mark_running()

            handler = self.handlers.get(job.name)
            if not handler:
                raise TaskNotFoundError(
                    f"No handler registered for job type: {job.name!r}",
                    details={
                        "job": job.name,
                        "registered": sorted(self.handlers.keys()),
                    },
                    hint=f"Register a handler with @task(name={job.name!r}) or task_registry.register(...).",
                )

            # Determine and cap timeout
            timeout = job.timeout
            if timeout is None and self.config.enforce_timeout:
                timeout = self.config.default_timeout
            if timeout is not None and timeout > self.config.max_timeout:
                self.logger.warning(
                    "JobProtocol %s timeout %ds exceeds maximum %ds, capping",
                    job.id,
                    timeout,
                    self.config.max_timeout,
                )
                timeout = self.config.max_timeout

            # Build timed execution callable; surfaces handler failures so
            # the retry policy can handle retries (middleware catches exceptions
            # and returns JobResult.fail rather than propagating them).
            async def _execute() -> Any:
                if timeout is not None:
                    try:
                        job_result_inner = await asyncio.wait_for(
                            self._execute_with_middleware(handler, job),
                            timeout=timeout,
                        )
                    except TimeoutError as te:
                        raise TaskTimeoutError(
                            f"JobProtocol timed out after {timeout}s",
                            details={
                                "job_id": job.id,
                                "job_name": job.name,
                                "timeout_seconds": timeout,
                            },
                            hint=f"Increase the timeout for job {job.name!r} or optimise the handler to complete faster.",
                        ) from te
                else:
                    job_result_inner = await self._execute_with_middleware(handler, job)

                if not job_result_inner.success:
                    raise TaskExecutionError(
                        job_result_inner.error or "handler execution failed",
                        details={
                            "job_id": job.id,
                            "job_name": job.name,
                            "retry_count": job.retry_count,
                        },
                        hint=f"Check the handler implementation for {job.name!r}. See job logs for the root cause.",
                    )
                return job_result_inner

            # Execute with retry policy if injected; otherwise single attempt (fail-open)
            if self._retry_policy is not None:
                inner_result = await self._retry_policy.execute(_execute)
            else:
                inner_result = await _execute()

            # === Success path ===
            duration = time.time() - start_time
            # ``inner_result`` is already a fully-formed JobResult produced by
            # the middleware chain (see execute_handler_through_middleware).
            # Re-wrapping it in another JobResult.ok(...) would nest a whole
            # JobResult inside `.data` instead of the handler's raw return
            # value, so unwrap its payload before building the final result.
            result = inner_result.data
            job_result = JobResult.ok(result, duration)
            job.mark_completed(job_result)
            await self._emit_action(
                "task.completed",
                TaskCompletedHook(task_name=job.name, task_id=job.id),
            )

            if self.result_store is not None:
                self._stamp_result(job_result, job)
                await self.result_store.store(job.id, job_result)

            if self.dashboard is not None:
                self.dashboard.record_execution(
                    task_name=job.name,
                    job_id=job.id,
                    duration_ms=duration * 1000,
                    success=True,
                    worker_id=self.worker_id,
                )

            if job.idempotency_key and self.idempotency_manager:
                await self.idempotency_manager.record_completion(
                    job.idempotency_key,
                    result,
                )

            self.stats.record_job(job_result)
            self.logger.info(
                "Worker %s completed job %s in %.2fs",
                self.worker_id,
                job.id,
                duration,
            )
            return Ok(job_result)

        except TaskError as e:
            # TaskError failures (including after retries exhausted by injected policy)
            await self._handle_job_failure(job, str(e), start_time)
            return Err(e)

        except Exception as e:  # noqa: BLE001 — job-failure boundary
            # ANY non-TaskError handler error (RuntimeError, AttributeError,
            # plain asyncio.TimeoutError, third-party SDK errors, ...) must
            # land in the failure path — stats, result store, DLQ — instead
            # of escaping to the work loop with the job stuck in RUNNING.
            # CancelledError is a BaseException and deliberately NOT caught,
            # so worker stop() still cancels cleanly.
            await self._handle_job_failure(job, str(e), start_time)
            task_error = TaskExecutionError(
                str(e),
                details={
                    "job_id": job.id,
                    "job_name": job.name,
                    "retry_count": job.retry_count,
                },
                hint=f"Check the handler implementation for {job.name!r}. See job logs for the root cause.",
            )
            return Err(task_error)

        finally:
            self.current_job = None

    async def _handle_job_failure(
        self,
        job: JobProtocol,
        error_msg: str,
        start_time: float,
    ) -> None:
        """Record final job failure and route to dead letter queue.

        Called for non-retriable failures or after retries are exhausted by the
        injected retry policy. Handles stats, result store, dashboard, and DLQ.

        Args:
            job: Failed job
            error_msg: Error message from the last failure
            start_time: JobProtocol start timestamp
        """
        duration = time.time() - start_time
        job_result = JobResult.fail(error_msg, job.retry_count, duration)
        self.stats.record_job(job_result)

        if self.result_store is not None:
            self._stamp_result(job_result, job)
            await self.result_store.store(job.id, job_result)

        if self.dashboard is not None:
            self.dashboard.record_execution(
                task_name=job.name,
                job_id=job.id,
                duration_ms=duration * 1000,
                success=False,
                error=error_msg,
                worker_id=self.worker_id,
            )

        job.mark_failed(error_msg)
        await self._emit_action(
            "task.failed",
            TaskFailedHook(task_name=job.name, task_id=job.id, reason=error_msg),
        )
        await self._send_to_dlq(job, error_msg)
        self.logger.error(
            "Worker %s job %s failed permanently after %s retries: %s",
            self.worker_id,
            job.id,
            job.retry_count,
            error_msg,
        )

    async def _send_to_dlq(self, job: JobProtocol, error_msg: str = "") -> None:
        """Send failed job to dead letter queue.

        Delegates to :func:`~quadkit.tasks.execution._failure_handling.send_to_dlq`.

        Args:
            job: Failed job to send to DLQ
            error_msg: Optional error message from the failure
        """
        await send_to_dlq(
            self.dlq,
            self.queue,
            job,
            error_msg,
            worker_id=self.worker_id,
            logger_instance=self.logger,
        )

    async def _resolve_dependencies(
        self,
        handler: Callable[..., Any],
        provided_args: tuple[Any, ...],
        provided_kwargs: dict[str, Any],
    ) -> tuple[list[Any], dict[str, Any]]:
        """Resolve handler dependencies from DI container.

        Delegates to :func:`~quadkit.tasks.execution._di_resolver.resolve_handler_dependencies`.

        Args:
            handler: Handler function to inspect
            provided_args: Arguments already provided by the job
            provided_kwargs: Keyword arguments already provided by the job

        Returns:
            Tuple of (resolved_args, resolved_kwargs) to pass to handler
        """
        container = getattr(self._services, "container", None)
        return await resolve_handler_dependencies(
            handler,
            provided_args,
            provided_kwargs,
            container,
            logger_instance=self.logger,
        )

    async def _run_handler(self, handler: Callable[..., Any], job: JobProtocol) -> Any:
        """Run the job handler function

        Args:
            handler: Handler function to execute
            job: JobProtocol with arguments

        Returns:
            Handler return value
        """
        return await invoke_handler(handler, *job.args, **job.kwargs)

    async def _execute_with_middleware(
        self,
        handler: Callable[..., Any],
        job: JobProtocol,
    ) -> JobResult:
        """Execute handler through the middleware pipeline.

        Delegates to
        :func:`~quadkit.tasks.execution._middleware_chain.execute_handler_through_middleware`.

        Args:
            handler: Handler function to execute
            job: JobProtocol to process

        Returns:
            JobResult from handler execution through middleware
        """
        return await execute_handler_through_middleware(
            self._middleware,
            handler,
            job,
            self._resolve_dependencies,
        )

    def get_stats(self) -> WorkerJobStats:
        """Get worker statistics

        Returns:
            Current worker statistics
        """
        return self.stats

    def is_busy(self) -> bool:
        """Check if worker is currently processing a job

        Returns:
            True if worker has a job in progress
        """
        return self.current_job is not None

    def get_progress_tracker(self, job_id: str) -> ProgressTracker | None:
        """Get a ProgressTracker for a job (opt-in for handlers).

        Handlers can use this to report progress. The worker must have
        a progress_store configured.

        Args:
            job_id: The job ID to track progress for

        Returns:
            ProgressTracker instance if progress_store is configured, None otherwise
        """
        if self.progress_store is None:
            return None
        return ProgressTracker(job_id, self.progress_store)


__all__ = ["TaskWorker", "TaskWorkerServices", "WorkerJobStats"]
