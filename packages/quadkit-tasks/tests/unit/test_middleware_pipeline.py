"""Tests for task middleware pipeline."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.tasks import task
from quadkit.tasks.middleware.core import (
    LoggingMiddleware,
    TaskExecutionContext,
    TaskMiddleware,
    TaskMiddlewarePipeline,
)
from quadkit.tasks.models.job import JobResult


def create_mock_job(job_id: str = "test-job") -> MagicMock:
    """Create a properly mocked task job."""
    job = MagicMock()
    job.id = job_id
    job.name = "test_task"
    job.args = ()
    job.kwargs = {}
    return job


class TestTaskExecutionContext:
    """Tests for TaskExecutionContext."""

    def test_create_context(self) -> None:
        """Creating a context should populate default values."""
        job = create_mock_job()
        ctx = TaskExecutionContext(job=job)

        assert ctx.job is job
        assert ctx.start_time == 0.0
        assert ctx.end_time == 0.0
        assert ctx.duration_ms == 0.0
        assert ctx.result is None
        assert ctx.metadata == {}

    def test_context_with_metadata(self) -> None:
        """Explicit metadata should be preserved."""
        job = create_mock_job()
        ctx = TaskExecutionContext(job=job, metadata={"key": "value"})

        assert ctx.metadata == {"key": "value"}


class TestTaskMiddlewarePipeline:
    """Tests for TaskMiddlewarePipeline."""

    @pytest.mark.asyncio
    async def test_empty_pipeline_executes_handler(self) -> None:
        """An empty pipeline should still execute the handler."""
        pipeline = TaskMiddlewarePipeline()
        job = create_mock_job()
        handler = AsyncMock(return_value=JobResult.ok(data={"test": "data"}))

        result = await pipeline.execute(job, handler)

        handler.assert_called_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_pipeline_calls_before_execute(self) -> None:
        """Middleware ``before_execute`` hooks should run."""
        pipeline = TaskMiddlewarePipeline()
        middleware = AsyncMock(spec=TaskMiddleware)
        pipeline.add(middleware)

        job = create_mock_job()
        handler = AsyncMock(return_value=JobResult.ok())

        await pipeline.execute(job, handler)

        middleware.before_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_calls_after_execute_on_success(self) -> None:
        """Middleware ``after_execute`` hooks should run after success."""
        pipeline = TaskMiddlewarePipeline()
        middleware = AsyncMock(spec=TaskMiddleware)
        pipeline.add(middleware)

        job = create_mock_job()
        handler = AsyncMock(return_value=JobResult.ok())

        await pipeline.execute(job, handler)

        middleware.after_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_calls_on_error_on_failure(self) -> None:
        """Middleware ``on_error`` hooks should run when the handler raises."""
        pipeline = TaskMiddlewarePipeline()
        middleware = AsyncMock(spec=TaskMiddleware)
        pipeline.add(middleware)

        job = create_mock_job()
        handler = AsyncMock(side_effect=ValueError("test error"))

        with pytest.raises(ValueError):
            await pipeline.execute(job, handler)

        middleware.on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_multiple_middleware_order(self) -> None:
        """Adding multiple middleware should preserve hook execution order."""
        pipeline = TaskMiddlewarePipeline()
        middle1 = AsyncMock(spec=TaskMiddleware)
        middle2 = AsyncMock(spec=TaskMiddleware)
        pipeline.add(middle1)
        pipeline.add(middle2)

        job = create_mock_job()
        handler = AsyncMock(return_value=JobResult.ok())

        await pipeline.execute(job, handler)

        assert len(middle1.before_execute.call_args_list) == 1

    @pytest.mark.asyncio
    async def test_pipeline_context_passed_to_middleware(self) -> None:
        """Middleware should receive a TaskExecutionContext instance."""
        pipeline = TaskMiddlewarePipeline()
        middleware = AsyncMock(spec=TaskMiddleware)
        pipeline.add(middleware)

        job = create_mock_job("test-job")
        handler = AsyncMock(return_value=JobResult.ok())

        await pipeline.execute(job, handler)

        assert middleware.before_execute.call_count == 1
        ctx = middleware.before_execute.call_args[0][0]
        assert isinstance(ctx, TaskExecutionContext)
        assert ctx.job is job

    @pytest.mark.asyncio
    async def test_pipeline_records_duration(self) -> None:
        """Execution duration should be captured in the result."""
        pipeline = TaskMiddlewarePipeline()

        async def slow_handler() -> JobResult:
            await asyncio.sleep(0.01)
            return JobResult.ok()

        job = create_mock_job()
        result = await pipeline.execute(job, slow_handler)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_pipeline_awaits_task_wrappers(self) -> None:
        """Callable wrappers returned by ``@task`` should be awaited correctly."""
        pipeline = TaskMiddlewarePipeline()
        job = create_mock_job()
        job.args = (5,)

        @task(name="test_task")
        async def handler(value: int) -> int:
            return value * 2

        result = await pipeline.execute(job, handler)

        assert result.success is True
        assert result.data == 10

    @pytest.mark.asyncio
    async def test_pipeline_failure_result_sanitizes_exception_text(self) -> None:
        """Failure snapshots never retain private exception messages."""
        class CaptureContext(TaskMiddleware):
            context: TaskExecutionContext | None = None

            async def on_error(
                self, ctx: TaskExecutionContext, error: Exception
            ) -> None:
                self.context = ctx

        private_error = "private /srv/app/users/user-42 traceback=secret"
        capture = CaptureContext()
        pipeline = TaskMiddlewarePipeline()
        pipeline.add(capture)

        async def fail() -> None:
            raise ValueError(private_error)

        with pytest.raises(ValueError):
            await pipeline.execute(create_mock_job(), fail)

        assert capture.context is not None
        assert capture.context.result is not None
        assert capture.context.result.error == "Task failed (ValueError)"
        assert private_error not in str(capture.context.result.error)
        assert "/srv/app" not in str(capture.context.result.error)
        assert "user-42" not in str(capture.context.result.error)

    @pytest.mark.asyncio
    async def test_logging_middleware_omits_ids_and_exception_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Task logs keep only status, duration, and exception type."""
        import quadkit.tasks.middleware.core as middleware_module

        logger = MagicMock()
        monkeypatch.setattr(middleware_module, "logger", logger)
        private_job_id = "private-job-id-42"
        private_task_name = "private-user-task"
        private_error = "private /srv/app/users/user-42 traceback=secret"
        job = create_mock_job(private_job_id)
        job.name = private_task_name
        context = TaskExecutionContext(
            job=job,
            duration_ms=12.5,
            result=JobResult.fail("Task failed (ValueError)"),
        )
        middleware = LoggingMiddleware()

        await middleware.before_execute(context)
        await middleware.on_error(context, ValueError(private_error))
        await middleware.after_execute(context)

        logger.info.assert_any_call("task.started")
        logger.info.assert_any_call(
            "task.finished",
            status="fail",
            duration_ms=12.5,
        )
        logger.error.assert_called_once_with(
            "task.failed",
            error_type="ValueError",
        )
        logged = repr(logger.mock_calls)
        assert private_job_id not in logged
        assert private_task_name not in logged
        assert private_error not in logged
        assert "/srv/app" not in logged
        assert "user-42" not in logged
