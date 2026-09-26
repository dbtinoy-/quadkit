"""Default middleware pipeline construction and handler execution.

Builds the built-in middleware chain (logging, metrics, timeout) and runs
a job handler through a :class:`TaskMiddlewarePipeline`, keeping the
worker loop free of middleware plumbing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import time
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.tasks.execution._invoke import invoke_handler
from quadkit.tasks.middleware.core import (
    TaskExecutionContext,
    TaskMiddlewarePipeline,
)

logger = get_logger(__name__)
from quadkit.tasks.models.job import JobResult

if TYPE_CHECKING:
    from quadkit.tasks.config import TaskWorkerConfig
    from quadkit.tasks.models.job import JobProtocol

__all__ = ["create_default_pipeline", "execute_handler_through_middleware"]

DependencyResolver = Callable[
    [Callable[..., Any], tuple[Any, ...], dict[str, Any]],
    Awaitable[tuple[list[Any], dict[str, Any]]],
]


def create_default_pipeline(config: TaskWorkerConfig) -> TaskMiddlewarePipeline:
    """Create default middleware pipeline with built-in middleware.

    Args:
        config: Worker configuration controlling default/max timeouts.

    Returns:
        TaskMiddlewarePipeline with default middleware
    """
    from quadkit.tasks.middleware.core import (
        LoggingMiddleware,
        MetricsMiddleware,
        TimeoutMiddleware,
    )

    pipeline = TaskMiddlewarePipeline()
    pipeline.add(LoggingMiddleware())
    pipeline.add(MetricsMiddleware())
    pipeline.add(
        TimeoutMiddleware(
            default_timeout=config.default_timeout,
            max_timeout=config.max_timeout,
        )
    )
    return pipeline


async def execute_handler_through_middleware(
    pipeline: TaskMiddlewarePipeline,
    handler: Callable[..., Any],
    job: JobProtocol,
    resolve_dependencies: DependencyResolver,
) -> JobResult:
    """Execute a handler through the middleware pipeline.

    Before-hooks run first, then handler dependencies are resolved from
    the DI container, then execution happens through timeout middleware
    when available, then after-hooks run.

    Args:
        pipeline: The middleware pipeline to run through.
        handler: Handler function to execute
        job: JobProtocol to process
        resolve_dependencies: Callable resolving container-provided
            arguments for the handler.

    Returns:
        JobResult from handler execution through middleware
    """
    # Create execution context for middleware
    ctx = TaskExecutionContext(job=job)

    # Before hooks - call all middleware before_execute
    for mw in pipeline._middleware:
        await mw.before_execute(ctx)

    # Check for timeout middleware and use it for execution
    timeout_middleware = None
    for mw in pipeline._middleware:
        if hasattr(mw, "execute_with_timeout"):
            timeout_middleware = mw
            break

    # Resolve handler dependencies from container before execution
    resolved_args, resolved_kwargs = await resolve_dependencies(
        handler, job.args, job.kwargs
    )
    # Merge resolved kwargs with job kwargs (job kwargs take precedence)
    final_kwargs = {**resolved_kwargs, **job.kwargs}

    # Execute handler with timeout enforcement if available
    ctx.start_time = time.monotonic()
    try:
        if timeout_middleware:
            ctx.result = await timeout_middleware.execute_with_timeout(
                handler,
                job,
                ctx,
                resolved_args,
                final_kwargs,
            )
        else:
            result_data = await invoke_handler(
                handler,
                *resolved_args,
                **final_kwargs,
            )
            duration = time.monotonic() - ctx.start_time
            ctx.result = JobResult.ok(result_data, duration)
    except Exception as exc:  # noqa: BLE001 — handler-failure boundary
        # ANY handler error becomes a failed JobResult so metrics/after
        # hooks still observe the failure.
        duration = time.monotonic() - ctx.start_time
        ctx.result = JobResult.fail(str(exc), job.retry_count, duration)
    finally:
        # After hooks run on success AND failure, isolated per middleware.
        for mw in pipeline._middleware:
            try:
                await mw.after_execute(ctx)
            except Exception:  # noqa: BLE001 — handler isolation
                logger.exception("Error in middleware after_execute")

    return ctx.result
