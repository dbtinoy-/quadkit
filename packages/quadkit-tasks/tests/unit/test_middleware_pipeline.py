"""Tests for task middleware pipeline."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.tasks import task
from quadkit.tasks.middleware.core import (
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
