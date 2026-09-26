"""Runtime hook emission tests for quadkit-tasks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.contracts.core import HookRegistryProtocol
from quadkit.hooks.registry import HookRegistry
from quadkit.tasks.backends.memory import MemoryTaskQueue
from quadkit.tasks.di.provider import TaskProvider
from quadkit.tasks.execution._lifecycle import TaskWorkerServices
from quadkit.tasks.execution.pool import WorkerPool
from quadkit.tasks.execution.worker import TaskWorker
from quadkit.tasks.hooks import TaskCompletedHook, TaskEnqueuedHook, TaskFailedHook
from quadkit.tasks.models.job import JobProtocol


class _ContainerStub:
    def __init__(
        self,
        *,
        optional: dict[type[object], object] | None = None,
        required: dict[type[object], object] | None = None,
    ) -> None:
        self._optional = optional or {}
        self._required = required or {}

    async def resolve_optional(self, contract: type[object]) -> object | None:
        return self._optional.get(contract)

    async def resolve(self, contract: type[object]) -> object | None:
        return self._required.get(contract)


@pytest.mark.asyncio
async def test_memory_backend_enqueue_emits_task_queued() -> None:
    """Successful memory enqueue should emit the queued lifecycle hook once."""
    hooks = HookRegistry("tasks-tests")
    seen: list[TaskEnqueuedHook] = []

    async def record(*, payload: TaskEnqueuedHook) -> None:
        seen.append(payload)

    hooks.register_action("task.queued", record)
    queue = MemoryTaskQueue()
    queue.set_hook_registry(hooks)

    result = await queue.enqueue(JobProtocol(id="job-1", name="send_email"))

    assert result.is_ok()
    assert seen == [TaskEnqueuedHook(task_name="send_email", queue_name="tasks")]


@pytest.mark.asyncio
async def test_worker_success_emits_task_completed() -> None:
    """Worker success should emit the completed lifecycle hook after completion."""
    hooks = HookRegistry("tasks-tests")
    seen: list[TaskCompletedHook] = []

    async def handler() -> str:
        return "done"

    async def record(*, payload: TaskCompletedHook) -> None:
        seen.append(payload)

    hooks.register_action("task.completed", record)
    worker = TaskWorker(
        "worker-1",
        queue=AsyncMock(),
        handler_registry={"send_email": handler},
        services=TaskWorkerServices(hooks=hooks),
    )
    job = JobProtocol(id="job-1", name="send_email")

    result = await worker._execute_job(job)

    assert result.is_ok()
    assert job.is_completed
    assert seen == [TaskCompletedHook(task_name="send_email", task_id="job-1")]


@pytest.mark.asyncio
async def test_worker_terminal_failure_emits_task_failed() -> None:
    """Worker terminal failure should emit the failed lifecycle hook once."""
    hooks = HookRegistry("tasks-tests")
    seen: list[TaskFailedHook] = []

    async def handler() -> str:
        raise RuntimeError("boom")

    async def record(*, payload: TaskFailedHook) -> None:
        seen.append(payload)

    hooks.register_action("task.failed", record)
    worker = TaskWorker(
        "worker-1",
        queue=AsyncMock(),
        handler_registry={"send_email": handler},
        services=TaskWorkerServices(hooks=hooks),
    )
    job = JobProtocol(id="job-1", name="send_email", max_retries=0)

    result = await worker._execute_job(job)

    assert result.is_err()
    assert job.is_failed
    assert len(seen) == 1
    assert seen[0].task_name == "send_email"
    assert seen[0].task_id == "job-1"
    assert seen[0].reason == job.last_error
    assert "boom" in seen[0].reason


@pytest.mark.asyncio
async def test_provider_boot_wires_hooks_into_primary_queue_and_worker_pool() -> None:
    """Provider boot should wire hooks into the primary queue and worker pool."""
    hooks = HookRegistry("tasks-tests")
    primary_queue = MagicMock()
    primary_queue.set_hook_registry = MagicMock()
    primary_queue.close = AsyncMock()
    primary_queue.get_task_count = AsyncMock(return_value=0)
    provider = TaskProvider(
        queue=primary_queue,
        worker_count=1,
        enable_scheduler=False,
    )
    container = _ContainerStub(optional={HookRegistryProtocol: hooks})

    with patch.object(WorkerPool, "start", new=AsyncMock()):
        await provider.boot(container)

    primary_queue.set_hook_registry.assert_called_once_with(hooks)
    assert provider.worker_pool is not None
    assert provider.worker_pool._hooks is hooks


@pytest.mark.asyncio
async def test_worker_pool_scale_to_propagates_hooks_to_new_workers() -> None:
    """Workers created during later scale-up should inherit the configured hooks."""
    hooks = HookRegistry("tasks-tests")
    pool = WorkerPool(
        queue=AsyncMock(),
        handler_registry={},
        size=0,
        hooks=hooks,
    )

    with patch.object(TaskWorker, "start", new=AsyncMock()):
        await pool.scale_to(1)

    assert len(pool.workers) == 1
    assert pool.workers[0]._hooks is hooks
