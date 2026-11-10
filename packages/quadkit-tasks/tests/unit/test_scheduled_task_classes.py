"""Unit tests for ScheduledTask and class-based @task / @scheduled execution."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from quadkit.di.container import Container
from quadkit.tasks import (
    HandlerRegistry,
    JobProtocol,
    Priority,
    ScheduledTask,
    TaskWorker,
    TaskWorkerServices,
    create_memory_task_provider,
    scheduled,
    task,
)


class _DatabaseService:
    def __init__(self, tag: str = "primary") -> None:
        self.tag = tag


class _OptionalBridge:
    def __init__(self) -> None:
        self.called = True


def test_scheduled_task_validates_async_execute_at_subclass_time() -> None:
    """Reject missing or synchronous execute() on concrete subclasses."""
    with pytest.raises(TypeError, match="must define an async 'execute"):

        class _MissingExecute(ScheduledTask):
            pass

    with pytest.raises(TypeError, match="must be an async coroutine method"):

        class _SyncExecute(ScheduledTask):
            def execute(self) -> None:
                return None

    class _AbstractBase(ScheduledTask, abstract=True):
        pass

    assert issubclass(_AbstractBase, ScheduledTask)


@pytest.mark.asyncio
async def test_scheduled_class_preserves_type_identity_and_executes_via_worker() -> (
    None
):
    """Execute a @scheduled ScheduledTask class through TaskWorker with DI."""
    recorded: list[tuple[str, bool, str | None]] = []

    @scheduled(
        cron="0 3 * * *",
        name="class-affinity-sync",
        priority=Priority.LOW,
        max_retries=2,
        timeout=120,
    )
    class _AffinitySyncTask(ScheduledTask):
        async def execute(
            self,
            db: _DatabaseService,
            bridge: _OptionalBridge | None = None,
            since: str | None = None,
        ) -> str:
            recorded.append((db.tag, bridge is not None, since))
            return f"synced:{db.tag}"

    # Class identity and direct instantiation remain intact
    assert isinstance(_AffinitySyncTask, type)
    assert issubclass(_AffinitySyncTask, ScheduledTask)
    direct = _AffinitySyncTask()
    assert isinstance(direct, _AffinitySyncTask)
    assert await direct.execute(db=_DatabaseService("direct")) == "synced:direct"

    # Full TaskProvider registration + TaskWorker DI execution
    container = Container()
    container.singleton(_DatabaseService, _DatabaseService("injected"))
    container.singleton(_OptionalBridge, _OptionalBridge())

    provider = create_memory_task_provider()
    await provider.register(container)
    await provider.boot(container)
    try:
        provider.register_scheduled_task(_AffinitySyncTask)
        assert provider.registry.get("class-affinity-sync") is _AffinitySyncTask

        worker = TaskWorker(
            "worker-test",
            queue=MagicMock(),
            handler_registry={"class-affinity-sync": _AffinitySyncTask},
            services=TaskWorkerServices(container=container),
        )
        job_result = await worker._execute_job(
            JobProtocol(id="j-1", name="class-affinity-sync"),
        )
        assert job_result.is_ok()
        assert job_result.unwrap().data == "synced:injected"
        assert recorded[-1] == ("injected", True, None)
    finally:
        await provider.shutdown()


@pytest.mark.asyncio
async def test_task_class_works_in_handler_registry() -> None:
    """Execute a @task ScheduledTask class directly via HandlerRegistry."""

    @task(name="compute-summary")
    class _SummaryTask(ScheduledTask):
        async def execute(self, multiplier: int) -> dict[str, Any]:
            return {"total": multiplier * 7}

    registry = HandlerRegistry()
    registry.register("compute-summary", _SummaryTask)
    out = await registry.execute(
        JobProtocol(id="j-2", name="compute-summary", args=(6,)),
    )
    assert out == {"total": 42}
