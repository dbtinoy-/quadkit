"""Task middleware pipeline for cross-cutting concerns.

Provides pre/post hooks around task execution for logging,
metrics, validation, timeouts, and custom logic.

Example:
    pipeline = TaskMiddlewarePipeline()
    pipeline.add(LoggingMiddleware())
    pipeline.add(MetricsMiddleware())
    pipeline.add(TimeoutMiddleware(default_timeout=30))

    result = await pipeline.execute(job, handler)
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
import time
from typing import Any

from quadkit.logging import get_logger
from quadkit.tasks.models.job import JobProtocol, JobResult

logger = get_logger(__name__)


@dataclass
class TaskExecutionContext:
    """Context passed through the middleware pipeline."""

    job: JobProtocol
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    result: JobResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskMiddleware(ABC):
    """Abstract base for task middleware."""

    async def before_execute(self, ctx: TaskExecutionContext) -> None:
        """Called before task execution. Override to modify or log."""

    async def after_execute(self, ctx: TaskExecutionContext) -> None:
        """Called after task execution. Override to observe or log."""

    async def on_error(
        self,
        ctx: TaskExecutionContext,
        error: Exception,
    ) -> None:
        """Called when task execution fails."""


class TaskMiddlewarePipeline:
    """Chains middleware around task execution."""

    def __init__(self) -> None:
        self._middleware: list[TaskMiddleware] = []

    def add(self, middleware: TaskMiddleware) -> None:
        """Append a middleware instance to the pipeline."""
        self._middleware.append(middleware)

    async def execute(
        self,
        job: JobProtocol,
        handler: Any,
    ) -> JobResult:
        """Execute a job through the middleware pipeline.

        Args:
            job: The job to execute.
            handler: The async handler function.

        Returns:
            JobResult from execution.
        """
        # Imported here to avoid a module-level cycle: importing
        # quadkit.tasks.execution (via _invoke) would re-enter this module
        # while it is still partially initialised.
        from quadkit.tasks.execution._invoke import invoke_handler

        ctx = TaskExecutionContext(job=job)

        # Before hooks
        for mw in self._middleware:
            await mw.before_execute(ctx)

        # Execute
        ctx.start_time = time.monotonic()
        try:
            result_data = await invoke_handler(handler, *job.args, **job.kwargs)

            duration = (time.monotonic() - ctx.start_time) * 1000
            ctx.duration_ms = duration
            ctx.result = JobResult.ok(data=result_data, duration=duration / 1000)
        except Exception as exc:
            ctx.end_time = time.monotonic()
            ctx.duration_ms = (ctx.end_time - ctx.start_time) * 1000
            ctx.result = JobResult.fail(str(exc), duration=ctx.duration_ms / 1000)

            for mw in reversed(self._middleware):
                try:
                    await mw.on_error(ctx, exc)
                except Exception:  # noqa: BLE001 — handler isolation
                    logger.exception("Error in middleware on_error")

            raise
        finally:
            ctx.end_time = time.monotonic()
            for mw in reversed(self._middleware):
                try:
                    await mw.after_execute(ctx)
                except Exception:  # noqa: BLE001 — handler isolation
                    logger.exception("Error in middleware after_execute")

        return ctx.result


# ------------------------------------------------------------------
# Built-in Middleware
# ------------------------------------------------------------------


class LoggingMiddleware(TaskMiddleware):
    """Logs task start, completion, and failures."""

    async def before_execute(self, ctx: TaskExecutionContext) -> None:
        """Log task start before execution."""
        logger.info(
            "TASK START [%s] job=%s",
            ctx.job.name,
            ctx.job.id,
        )

    async def after_execute(self, ctx: TaskExecutionContext) -> None:
        """Log task completion status and duration after execution."""
        status = "OK" if ctx.result and ctx.result.success else "FAIL"
        logger.info(
            "TASK %s [%s] job=%s (%.1fms)",
            status,
            ctx.job.name,
            ctx.job.id,
            ctx.duration_ms,
        )

    async def on_error(
        self,
        ctx: TaskExecutionContext,
        error: Exception,
    ) -> None:
        """Log the error when a task raises an exception."""
        logger.error(
            "TASK ERROR [%s] job=%s: %s",
            ctx.job.name,
            ctx.job.id,
            error,
        )


class MetricsMiddleware(TaskMiddleware):
    """Collects per-task-type execution metrics."""

    def __init__(self) -> None:
        self._metrics: dict[str, dict[str, Any]] = {}
        self._total_executed = 0
        self._total_failed = 0

    async def after_execute(self, ctx: TaskExecutionContext) -> None:
        """Record execution metrics for the completed task."""
        self._total_executed += 1
        name = ctx.job.name

        if name not in self._metrics:
            self._metrics[name] = {
                "count": 0,
                "total_ms": 0.0,
                "min_ms": float("inf"),
                "max_ms": 0.0,
                "errors": 0,
            }

        m = self._metrics[name]
        m["count"] += 1
        m["total_ms"] += ctx.duration_ms
        m["min_ms"] = min(m["min_ms"], ctx.duration_ms)
        m["max_ms"] = max(m["max_ms"], ctx.duration_ms)

    async def on_error(
        self,
        ctx: TaskExecutionContext,
        error: Exception,
    ) -> None:
        """Increment failure counter for the task type that raised an error."""
        self._total_failed += 1
        name = ctx.job.name
        if name in self._metrics:
            self._metrics[name]["errors"] += 1

    def get_stats(self) -> dict[str, Any]:
        """Return aggregated execution statistics keyed by task name."""
        return {
            "total_executed": self._total_executed,
            "total_failed": self._total_failed,
            "per_task": {
                name: {
                    **m,
                    "avg_ms": round(m["total_ms"] / m["count"], 2)
                    if m["count"] > 0
                    else 0,
                }
                for name, m in self._metrics.items()
            },
        }


class TimeoutMiddleware(TaskMiddleware):
    """Enforces execution timeout on tasks.

    Uses asyncio.wait_for to enforce timeout on task execution.
    """

    def __init__(
        self,
        default_timeout: float = 300.0,
        max_timeout: float | None = None,
    ) -> None:
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout

    async def before_execute(self, ctx: TaskExecutionContext) -> None:
        """Compute and store the effective timeout in the execution context metadata."""
        timeout = ctx.job.timeout or self.default_timeout
        # Cap at max_timeout if set
        if self.max_timeout is not None and timeout > self.max_timeout:
            timeout = self.max_timeout
        ctx.metadata["_timeout"] = timeout

    async def execute_with_timeout(
        self,
        handler: Any,
        job: JobProtocol,
        ctx: TaskExecutionContext,
        resolved_args: list[Any] | None = None,
        resolved_kwargs: dict[str, Any] | None = None,
    ) -> JobResult:
        """Execute handler with timeout enforcement.

        Args:
            handler: The handler to execute
            job: The job being executed
            ctx: Execution context
            resolved_args: Pre-resolved positional arguments (from DI)
            resolved_kwargs: Pre-resolved keyword arguments (from DI)

        Returns:
            JobResult from execution
        """
        import asyncio
        import time

        timeout = ctx.metadata.get("_timeout", self.default_timeout)

        # Use resolved args/kwargs if provided, otherwise fall back to job args/kwargs
        args_to_use = resolved_args if resolved_args is not None else list(job.args)
        kwargs_to_use = (
            resolved_kwargs if resolved_kwargs is not None else dict(job.kwargs)
        )

        async def run_handler() -> Any:
            # Imported here to avoid a module-level cycle: importing
            # quadkit.tasks.execution (via _invoke) would re-enter this
            # module while it is still partially initialised.
            from quadkit.tasks.execution._invoke import invoke_handler

            return await invoke_handler(handler, *args_to_use, **kwargs_to_use)

        start_time = time.monotonic()
        try:
            result_data = await asyncio.wait_for(run_handler(), timeout=timeout)
            duration = time.monotonic() - start_time
            return JobResult.ok(result_data, duration)
        except TimeoutError:
            duration = time.monotonic() - start_time
            return JobResult.fail(
                f"Task timed out after {timeout}s",
                job.retry_count,
                duration,
            )
        except Exception as exc:  # noqa: BLE001 — handler-failure boundary
            # ANY handler error becomes a failed JobResult (never escapes
            # the middleware layer as a raw exception).
            duration = time.monotonic() - start_time
            return JobResult.fail(str(exc), job.retry_count, duration)
