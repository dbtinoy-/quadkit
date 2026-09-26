"""Tests for the task provider operations mixin."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.tasks.decorators import scheduled
from quadkit.tasks.exceptions import TaskRegistrationError
from quadkit.tasks.models.job import JobProtocol


class _FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[JobProtocol] = []

    async def enqueue(self, job: JobProtocol) -> None:
        self.enqueued.append(job)


def _job() -> JobProtocol:
    return JobProtocol(
        id="job-1",
        name="my-task",
        args=(),
        kwargs={},
        priority=1,
        max_retries=0,
        status="pending",
    )


class _FakeScheduler:
    def __init__(self) -> None:
        self.scheduled: list[tuple[Any, str, str | None]] = []
        self.unscheduled: list[str] = []
        self.scheduled_jobs: dict[str, Any] = {}

    def schedule_job_sync(self, template: Any, cron: str, job_id: str | None) -> str | None:
        self.scheduled.append((template, cron, job_id))
        return job_id or "scheduled-id"

    def unschedule_job_sync(self, job_id: str) -> bool:
        self.unscheduled.append(job_id)
        return True


class _FakeWorkerPool:
    def __init__(self) -> None:
        self.refreshed = 0
        self.stats = {"workers": 2}

    def refresh_handlers(self) -> None:
        self.refreshed += 1

    def get_pool_stats(self) -> dict[str, Any]:
        return self.stats


def _provider(
    scheduler: Any = None,
    worker_pool: Any = None,
    enable_scheduler: bool = False,
) -> Any:
    from quadkit.tasks.di.provider import TaskProvider

    p = TaskProvider(queue=_FakeQueue(), enable_scheduler=enable_scheduler)
    p.scheduler = scheduler
    p.worker_pool = worker_pool
    return p


class TestRegisterHandler:
    """Operations-mixin behavior on a real TaskProvider."""
    def test_registers_and_refreshes(self) -> None:  # noqa: D102
        p = _provider(worker_pool=_FakeWorkerPool())

        async def handler(x: int) -> int:
            return x

        p.register_handler("t1", handler)
        assert p.registry.get_handler("t1") is not None
        assert p.worker_pool.refreshed == 1

    def test_unwraps_decorated_handler(self) -> None:  # noqa: D102
        p = _provider()

        async def original(x: int) -> int:
            return x

        wrapper = lambda: None  # noqa: E731
        wrapper._func = original

        p.register_handler("t2", wrapper)
        assert p.registry.get_handler("t2") is original

    def test_bound_method_unwrapped(self) -> None:  # noqa: D102
        p = _provider()

        class _Svc:
            def job(self, x: int) -> int:
                return x

        svc = _Svc()
        p.register_handler("t3", svc.job)
        handler = p.registry.get_handler("t3")
        assert handler is not None


class TestIdempotencyBuilders:
    """Operations-mixin behavior on a real TaskProvider."""
    def test_build_idempotency_manager(self) -> None:  # noqa: D102
        from quadkit.tasks.execution.manager import IdempotencyManager

        p = _provider()

        class _Storage:
            async def get(self, key: str) -> Any:
                return None

            async def set(self, key: str, value: Any, **kw: Any) -> None:
                pass

        mgr = p.build_idempotency_manager(_Storage())
        assert isinstance(mgr, IdempotencyManager)

    def test_build_idempotent_task_manager(self) -> None:  # noqa: D102
        from quadkit.tasks.execution.manager import IdempotentTaskManager

        p = _provider()

        class _Storage:
            async def get(self, key: str) -> Any:
                return None

            async def set(self, key: str, value: Any, **kw: Any) -> None:
                pass

        mgr = p.build_idempotent_task_manager(
            p.queue, p.build_idempotency_manager(_Storage())
        )
        assert isinstance(mgr, IdempotentTaskManager)


class TestRegisterScheduledTask:
    """Operations-mixin behavior on a real TaskProvider."""
    def test_missing_task_name_raises(self) -> None:  # noqa: D102
        p = _provider()

        def plain() -> None:
            pass

        with pytest.raises(TaskRegistrationError, match="lacks _task_name"):
            p.register_scheduled_task(plain)

    def test_missing_cron_raises(self) -> None:  # noqa: D102
        p = _provider()

        async def t() -> None:
            pass

        t._task_name = "t"  # type: ignore[attr-defined]

        with pytest.raises(TaskRegistrationError, match="lacks _cron"):
            p.register_scheduled_task(t)

    def test_registers_and_schedules(self) -> None:  # noqa: D102
        from quadkit.tasks.decorators import scheduled

        sched = _FakeScheduler()
        p = _provider(scheduler=sched, enable_scheduler=True)

        @scheduled(cron="*/5 * * * *", name="s1")
        def t() -> None:
            pass

        p.register_scheduled_task(t)
        assert p.registry.get_handler("s1") is not None
        assert len(sched.scheduled) == 1
        assert sched.scheduled[0][1] == "*/5 * * * *"
        assert sched.scheduled[0][0].name == "s1"

    def test_scheduling_failure_rolls_back(self) -> None:  # noqa: D102
        class _FailingScheduler(_FakeScheduler):
            def schedule_job_sync(self, template: Any, cron: str, job_id: str | None) -> str | None:
                raise RuntimeError("sched boom")

        sched = _FailingScheduler()
        pool = _FakeWorkerPool()
        p = _provider(scheduler=sched, worker_pool=pool, enable_scheduler=True)

        @scheduled(cron="0 * * * *", name="s2")
        def t() -> None:
            pass

        with pytest.raises(RuntimeError, match="sched boom"):
            p.register_scheduled_task(t)
        # handler rolled back + workers refreshed
        assert p.registry.get_handler("s2") is None
        assert pool.refreshed >= 1

    def test_no_scheduler_still_registers(self) -> None:  # noqa: D102
        from quadkit.tasks.decorators import scheduled

        p = _provider(scheduler=None, enable_scheduler=False)

        @scheduled(cron="0 0 * * *", name="s3")
        def t() -> None:
            pass

        p.register_scheduled_task(t)
        assert p.registry.get_handler("s3") is not None


class TestEnqueueAndScheduling:
    """Operations-mixin behavior on a real TaskProvider."""
    @pytest.mark.asyncio
    async def test_enqueue_job_returns_id(self) -> None:  # noqa: D102
        p = _provider()
        job = _job()
        assert await p.enqueue_job(job) == "job-1"
        assert p.queue.enqueued == [job]

    @pytest.mark.asyncio
    async def test_internal_enqueue_delegates(self) -> None:  # noqa: D102
        p = _provider()
        job = _job()
        await p._enqueue_job(job)
        assert p.queue.enqueued == [job]

    def test_schedule_job_sync_delegates(self) -> None:  # noqa: D102
        sched = _FakeScheduler()
        p = _provider(scheduler=sched)
        job = _job()
        result = p.schedule_job_sync(job, "0 0 * * *", job_id="jid")
        assert result == "jid"
        assert sched.scheduled[0][0] is job

    def test_schedule_job_sync_without_scheduler(self) -> None:  # noqa: D102
        p = _provider(scheduler=None)
        assert p.schedule_job_sync(_job(), "0 0 * * *") is None

    def test_unschedule_job_sync(self) -> None:  # noqa: D102
        sched = _FakeScheduler()
        p = _provider(scheduler=sched)
        assert p.unschedule_job_sync("jid") is True
        assert sched.unscheduled == ["jid"]

    def test_unschedule_without_scheduler(self) -> None:  # noqa: D102
        p = _provider(scheduler=None)
        assert p.unschedule_job_sync("jid") is False


class TestStatsAndRefresh:
    """Operations-mixin behavior on a real TaskProvider."""
    def test_get_worker_stats(self) -> None:  # noqa: D102
        pool = _FakeWorkerPool()
        p = _provider(worker_pool=pool)
        assert p.get_worker_stats() == {"workers": 2}

    def test_get_worker_stats_none_without_pool(self) -> None:  # noqa: D102
        p = _provider(worker_pool=None)
        assert p.get_worker_stats() is None

    def test_get_scheduled_jobs_none_without_scheduler(self) -> None:  # noqa: D102
        p = _provider(scheduler=None)
        assert p.get_scheduled_jobs() is None

    def test_refresh_worker_handlers_no_pool(self) -> None:  # noqa: D102
        p = _provider(worker_pool=None)
        p.refresh_worker_handlers()  # must not raise

    def test_refresh_worker_handlers_with_pool(self) -> None:  # noqa: D102
        pool = _FakeWorkerPool()
        p = _provider(worker_pool=pool)
        p.refresh_worker_handlers()
        assert pool.refreshed == 1
