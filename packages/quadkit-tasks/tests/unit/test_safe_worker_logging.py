"""Regression coverage for worker and scheduler log privacy."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

import quadkit.tasks.backends.postgres as postgres_module
import quadkit.tasks.execution._concurrency as concurrency_module
import quadkit.tasks.scheduling.scheduler as scheduler_module
from quadkit.tasks.backends.postgres import PostgresTaskQueue
from quadkit.tasks.execution.pool import WorkerPool
from quadkit.tasks.execution.worker import TaskWorker, TaskWorkerServices
from quadkit.tasks.scheduling.scheduler import TaskScheduler
from quadkit.tasks.scheduling.templates import JobTemplateProtocol

_PRIVATE_ID = "PRIVATE_JOB_ID_SENTINEL"
_PRIVATE_ERROR = "PRIVATE_ERROR_SENTINEL /srv/private/users/42"


class _AsyncScope:
    async def __aenter__(self) -> _AsyncScope:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Provider:
    def __init__(self, execute: AsyncMock | None = None) -> None:
        self.connection = SimpleNamespace(execute=execute or AsyncMock())
        self.scoped_context = MagicMock(side_effect=_AsyncScope)
        self.get_scoped_connection = AsyncMock(return_value=self.connection)


@pytest.mark.asyncio
async def test_postgres_queue_logs_actions_without_task_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    monkeypatch.setattr(postgres_module, "logger", logger)
    queue = PostgresTaskQueue(provider=_Provider())

    job_id = await queue._enqueue({"secret": "payload"})
    await queue._ack(job_id)
    await queue._nack(job_id, requeue=False)
    await queue._nack(job_id, requeue=True, delay_seconds=7)

    assert logger.debug.call_args_list == [
        call("task.enqueued"),
        call("task.acknowledged"),
        call("task.nacked", requeued=False),
        call("task.nacked", requeued=True, delay_seconds=7),
    ]
    assert job_id not in repr(logger.mock_calls)
    assert _PRIVATE_ID not in repr(logger.mock_calls)
    assert _PRIVATE_ERROR not in repr(logger.mock_calls)


@pytest.mark.asyncio
async def test_postgres_row_count_warning_logs_only_error_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    monkeypatch.setattr(postgres_module, "logger", logger)

    class _BadRowCount:
        def __str__(self) -> str:
            return f"invalid count for {_PRIVATE_ID}: {_PRIVATE_ERROR}"

    queue = PostgresTaskQueue(provider=_Provider(AsyncMock(return_value=_BadRowCount())))
    await queue.requeue_stalled()

    assert logger.warning.call_count == 2
    for call in logger.warning.call_args_list:
        assert call.args == ("affected_rows_count_parse_failed",)
        assert call.kwargs == {"error_type": "ValueError"}
    assert _PRIVATE_ID not in repr(logger.mock_calls)
    assert _PRIVATE_ERROR not in repr(logger.mock_calls)


@pytest.mark.asyncio
async def test_scheduler_logs_do_not_include_job_ids_or_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    monkeypatch.setattr(scheduler_module, "logger", logger)
    scheduler = TaskScheduler()
    job_id = scheduler.schedule_job_sync(
        JobTemplateProtocol(name="private-user-task"),
        "* * * * *",
        job_id=_PRIVATE_ID,
    )
    scheduled = scheduler.get_scheduled_job(job_id)
    assert scheduled is not None
    scheduled.next_run = 0

    async def enqueue(_job: object) -> None:
        raise RuntimeError(_PRIVATE_ERROR)

    await scheduler._check_scheduled_jobs(enqueue)
    assert scheduler.disable_job(job_id)
    assert scheduler.enable_job(job_id)
    assert scheduler.unschedule_job_sync(job_id)

    logger.error.assert_called_once_with(
        "scheduler_job_enqueue_failed",
        error_type="RuntimeError",
    )
    assert "scheduler.job_scheduled" in repr(logger.mock_calls)
    assert "scheduler.job_disabled" in repr(logger.mock_calls)
    assert "scheduler.job_enabled" in repr(logger.mock_calls)
    assert "scheduler.job_unscheduled" in repr(logger.mock_calls)
    assert _PRIVATE_ID not in repr(logger.mock_calls)
    assert "private-user-task" not in repr(logger.mock_calls)
    assert _PRIVATE_ERROR not in repr(logger.mock_calls)


@pytest.mark.asyncio
async def test_worker_task_names_and_start_logs_omit_worker_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    worker_id = "PRIVATE_WORKER_ID_SENTINEL"
    worker = TaskWorker(
        worker_id,
        AsyncMock(),
        {},
        services=TaskWorkerServices(logger=logger),
    )
    captured: dict[str, str] = {}

    def create_tracked_task(coro, _task_set, *, name=None):
        coro.close()
        captured["name"] = name
        return object()

    monkeypatch.setattr(concurrency_module, "create_tracked_task", create_tracked_task)
    await worker.start()

    assert captured["name"] == "task_worker_loop"
    logger.info.assert_called_once_with("worker.started")
    assert worker_id not in repr(logger.mock_calls)

    manager_name: dict[str, str] = {}

    class _TaskManager:
        def create_critical_task(self, coro, *, name):
            coro.close()
            manager_name["name"] = name
            return object()

    managed_logger = MagicMock()
    managed_worker = TaskWorker(
        worker_id,
        AsyncMock(),
        {},
        services=TaskWorkerServices(
            logger=managed_logger,
            task_manager=_TaskManager(),
        ),
    )
    await managed_worker.start()

    assert manager_name["name"] == "task_worker"
    managed_logger.info.assert_called_once_with("worker.started")
    assert worker_id not in repr(managed_logger.mock_calls)


@pytest.mark.asyncio
async def test_pool_scale_logs_worker_count_without_worker_id() -> None:
    logger = MagicMock()
    pool = WorkerPool(
        queue=AsyncMock(),
        handler_registry={},
        size=1,
        logger=logger,
    )
    pool.logger = logger
    worker = MagicMock()
    worker.start = AsyncMock()
    pool._create_worker = MagicMock(return_value=worker)

    await pool.scale_to(2)

    logger.info.assert_any_call("worker_pool.worker_added")
    logger.info.assert_any_call("Worker pool scaled to %d workers", 2)
    assert "worker-2" not in repr(logger.mock_calls)
