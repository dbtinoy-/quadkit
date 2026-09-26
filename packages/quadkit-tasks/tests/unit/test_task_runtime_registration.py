"""Runtime task registration and wrapper execution tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

from quadkit.tasks import MemoryTaskQueue, task
from quadkit.tasks.decorators import _clear_registered_tasks, unwrap_task_handler
from quadkit.tasks.di.provider import TaskProvider
from quadkit.tasks.execution.registry import HandlerRegistry
from quadkit.tasks.execution.worker import TaskWorker
from quadkit.tasks.models.job import JobProtocol


class _ContainerStub:
    async def resolve_optional(self, contract: type[object]) -> object | None:
        return None

    async def resolve(self, contract: type[object]) -> object | None:
        return None


def _write_task_package(tmp_path: Path, package_name: str, module_name: str) -> str:
    package_root = tmp_path / package_name
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "__init__.py").write_text("")
    module_path = package_root / f"{module_name}.py"
    module_path.write_text(
        "from quadkit.tasks import scheduled, task\n\n"
        "@scheduled(cron='*/15 * * * *', name='cleanup')\n"
        "async def cleanup() -> dict[str, bool]:\n"
        "    return {'ok': True}\n\n"
        "@task(name='send_confirmation')\n"
        "async def send_confirmation(order_id: str) -> dict[str, str]:\n"
        "    return {'order_id': order_id}\n"
    )
    return f"{package_name}.{module_name}"


@pytest.mark.asyncio
async def test_task_provider_boot_discovers_already_imported_tasks() -> None:
    """Decorated tasks in imported application modules need no hand wiring."""
    _clear_registered_tasks()

    @task(name="already_imported")
    async def already_imported() -> dict[str, bool]:
        return {"ok": True}

    provider = TaskProvider(
        queue=MemoryTaskQueue(),
        worker_count=1,
        enable_scheduler=False,
    )
    try:
        await provider.boot(_ContainerStub())
        assert provider.registry.get("already_imported") is unwrap_task_handler(
            already_imported
        )
    finally:
        await provider.shutdown()
        _clear_registered_tasks()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_modules", "task_packages"),
    [(["demo_task_app.jobs"], []), ([], ["demo_task_app"])],
)
async def test_task_provider_boot_autodiscovers_decorated_tasks(
    tmp_path: Path,
    task_modules: list[str],
    task_packages: list[str],
) -> None:
    """Configured task modules and packages should register decorated tasks."""
    package_name = "demo_task_app"
    module_name = "jobs"
    module_path = _write_task_package(tmp_path, package_name, module_name)
    sys.path.insert(0, str(tmp_path))

    provider: TaskProvider | None = None
    try:
        provider = TaskProvider(
            queue=MemoryTaskQueue(),
            worker_count=1,
            enable_scheduler=True,
            task_modules=task_modules,
            task_packages=task_packages,
        )
        await provider.boot(_ContainerStub())

        handlers = provider.registry.to_dict()
        assert "cleanup" in handlers
        assert "send_confirmation" in handlers

        scheduled = provider.get_scheduled_jobs()
        assert scheduled is not None
        assert [(job["name"], job["cron"]) for job in scheduled["scheduled_jobs"]] == [
            ("cleanup", "*/15 * * * *")
        ]
    finally:
        if provider is not None:
            await provider.shutdown()
        _clear_registered_tasks((package_name,))
        sys.modules.pop(module_path, None)
        sys.modules.pop(package_name, None)
        sys.path = [entry for entry in sys.path if entry != str(tmp_path)]


def test_register_handler_unwraps_task_wrappers_and_refreshes_pool() -> None:
    """Late handler registrations should refresh workers and store raw callables."""
    provider = TaskProvider(queue=MemoryTaskQueue(), enable_scheduler=False)
    provider.worker_pool = MagicMock()

    @task(name="send_confirmation")
    async def send_confirmation(order_id: str) -> dict[str, str]:
        return {"order_id": order_id}

    provider.register_handler("send_confirmation", send_confirmation)

    assert provider.registry.get("send_confirmation") is unwrap_task_handler(
        send_confirmation
    )
    provider.worker_pool.refresh_handlers.assert_called_once_with()


@pytest.mark.asyncio
async def test_worker_run_handler_awaits_task_wrapper() -> None:
    """Callable task wrappers should execute their async bodies, not leak coroutines."""
    calls: list[int] = []

    @task(name="double")
    async def double(value: int) -> int:
        calls.append(value)
        return value * 2

    worker = TaskWorker(
        "worker-1",
        queue=MagicMock(),
        handler_registry={"double": double},
    )
    job = JobProtocol(id="job-1", name="double", args=(3,), max_retries=0)

    result = await worker._run_handler(double, job)

    assert result == 6
    assert calls == [3]


@pytest.mark.asyncio
async def test_handler_registry_execute_awaits_task_wrapper() -> None:
    """Registry dispatch should await wrapper objects returned by ``@task``."""
    registry = HandlerRegistry()

    @task(name="triple")
    async def triple(value: int) -> int:
        return value * 3

    registry.register("triple", triple)
    result = await registry.execute(JobProtocol(id="job-2", name="triple", args=(4,)))

    assert result == 12


@pytest.mark.asyncio
async def test_timeout_middleware_awaits_task_wrapper() -> None:
    """The timeout path is a fourth dispatch site; it must await too.

    `execute_with_timeout` is only reached when a timeout middleware is
    installed, so a fix that covered the worker and registry but not this path
    would look correct until someone enabled a task timeout — and then the
    wrapper's coroutine would be dropped exactly as before.
    """
    from quadkit.tasks.middleware.core import TaskExecutionContext, TimeoutMiddleware

    calls: list[int] = []

    @task(name="slow_double")
    async def slow_double(value: int) -> int:
        calls.append(value)
        return value * 2

    middleware = TimeoutMiddleware(default_timeout=5.0)
    ctx = TaskExecutionContext(job=JobProtocol(id="job-3", name="slow_double"))
    result = await middleware.execute_with_timeout(
        slow_double,
        ctx.job,
        ctx,
        resolved_args=[4],
        resolved_kwargs={},
    )

    assert result.success is True
    assert result.data == 8
    assert calls == [4]


@pytest.mark.asyncio
async def test_middleware_chain_awaits_task_wrapper() -> None:
    """The no-timeout middleware path must await the wrapper as well."""
    from quadkit.tasks.execution._middleware_chain import (
        execute_handler_through_middleware,
    )
    from quadkit.tasks.middleware.core import TaskMiddlewarePipeline

    calls: list[int] = []

    @task(name="chain_double")
    async def chain_double(value: int) -> int:
        calls.append(value)
        return value * 2

    async def resolve(
        _handler: object, args: object, kwargs: object
    ) -> tuple[list, dict]:
        return list(args), dict(kwargs)  # type: ignore[arg-type]

    job = JobProtocol(id="job-4", name="chain_double", args=(5,))
    result = await execute_handler_through_middleware(
        TaskMiddlewarePipeline(), chain_double, job, resolve
    )

    assert result.success is True
    assert result.data == 10
    assert calls == [5]


def test_a_late_plain_handler_reaches_the_pool_and_its_workers() -> None:
    """TASK-4: the pool's snapshot is refreshed for late registrations.

    The previous coverage asserted that ``refresh_handlers()`` was *called* on a
    mocked pool, which is satisfied by any implementation that keeps the pool
    stale. This walks the real objects: a worker created before the
    registration must be able to dispatch the task afterwards.
    """
    from quadkit.tasks.execution.pool import WorkerPool

    provider = TaskProvider(queue=MemoryTaskQueue(), enable_scheduler=False)
    pool = WorkerPool(MemoryTaskQueue(), provider.registry, size=0)
    provider.worker_pool = pool
    # ``size=0`` so no worker tasks are started; ``_create_worker`` is the
    # pool's own constructor for one, appended the way ``start()`` does it, so
    # this is a worker the pool knows about — created before the registration,
    # which is the case the boot-time snapshot broke.
    worker = pool._create_worker("worker-1")
    pool.workers.append(worker)

    @task(name="late_report")
    async def late_report(reason: str) -> str:
        return reason

    assert "late_report" not in worker.handlers

    provider.register_handler("late_report", late_report)

    assert "late_report" in pool.handlers
    assert "late_report" in worker.handlers
    # And the worker would take its async branch, per TASK-5.
    assert asyncio.iscoroutinefunction(worker.handlers["late_report"])
