"""The tasks admin widget handlers are registrable outside ``TaskProvider``.

``TasksAdminContributor`` mounts in any app that installs ``quadkit-tasks`` and
resolves its handlers from the DI container at boot, so an app that wires its
own queue must be able to register the same handlers.
"""

from __future__ import annotations

from typing import Any

from quadkit.tasks.admin.handlers.avg_duration import AvgDurationWidgetHandler
from quadkit.tasks.admin.handlers.tasks_summary import TasksSummaryWidgetHandler
from quadkit.tasks.admin.registration import register_admin_widget_handlers


class _RecordingRegistrar:
    """Minimal registrar recording transient registrations."""

    def __init__(self) -> None:
        self.transients: dict[str, Any] = {}

    def transient(self, service_type: Any, factory: Any = None, name: str = "") -> None:
        key = getattr(service_type, "__name__", str(service_type))
        self.transients[key] = factory if factory is not None else service_type


def test_registers_both_handlers() -> None:
    """Summary and duration widgets are both registered."""
    registrar = _RecordingRegistrar()
    register_admin_widget_handlers(registrar)
    assert set(registrar.transients) == {
        "TasksSummaryWidgetHandler",
        "AvgDurationWidgetHandler",
    }


def test_handlers_receive_the_wired_queue_and_pool() -> None:
    """The widgets report the queue/pool the app passes in."""
    class _Queue:
        async def get_task_count(self) -> int:  # pragma: no cover — shape only
            raise NotImplementedError

    class _Pool:
        def get_pool_stats(self) -> dict[str, Any]:  # pragma: no cover — shape only
            raise NotImplementedError

    queue, pool = _Queue(), _Pool()
    registrar = _RecordingRegistrar()
    register_admin_widget_handlers(registrar, queue=queue, worker_pool=pool)

    summary = registrar.transients["TasksSummaryWidgetHandler"]()
    duration = registrar.transients["AvgDurationWidgetHandler"]()
    assert summary._queue_provider is queue
    assert summary._pool_provider is pool
    assert duration._pool_provider is pool


def test_handlers_are_usable_without_a_runtime() -> None:
    """With no queue or pool wired the widgets report zeros, not failures."""
    registrar = _RecordingRegistrar()
    register_admin_widget_handlers(registrar)

    assert isinstance(
        registrar.transients["TasksSummaryWidgetHandler"](), TasksSummaryWidgetHandler
    )
    assert isinstance(
        registrar.transients["AvgDurationWidgetHandler"](), AvgDurationWidgetHandler
    )


async def test_summary_reports_zeros_without_a_runtime() -> None:
    """The dashboard renders a value for every cell even with no runtime."""
    from quadkit.contracts.admin import WidgetParams

    handler = TasksSummaryWidgetHandler()
    payload = (await handler.get_data(WidgetParams())).unwrap()
    assert [stat.value for stat in payload.stats] == ["0", "0", "0", "0"]


class _ContainerStub:
    """Container shaped enough for ``TaskProvider`` registration."""

    async def resolve_optional(self, contract: type[object]) -> object | None:
        return None

    async def resolve(self, contract: type[object]) -> object | None:
        return None

    def singleton(self, service_type: object, factory: object = None, name: str = "") -> None:
        return None

    def transient(self, service_type: object, factory: object = None, name: str = "") -> None:
        return None


async def test_widgets_report_a_live_pool_and_queue() -> None:
    """The widgets report the numbers an executed job actually produced.

    Registration alone is not evidence: a handler can be registered against a
    queue no worker drains, or a pool that never runs a handler, and both
    widgets would still render. This drives the real
    :class:`~quadkit.tasks.di.provider.TaskProvider` — queue, worker pool and
    handler registry — through one successful and one failing job, then reads
    the payloads the dashboard renders.
    """
    import asyncio

    from quadkit.contracts.admin import WidgetParams
    from quadkit.tasks.backends.memory import MemoryTaskQueue
    from quadkit.tasks.di.provider import TaskProvider
    from quadkit.tasks.models.job import JobProtocol

    provider = TaskProvider(
        queue=MemoryTaskQueue(),
        worker_count=1,
        enable_scheduler=False,
    )
    await provider.boot(_ContainerStub())
    pool = provider.worker_pool
    try:

        async def _succeeds(**kwargs: object) -> dict[str, bool]:
            return {"ok": True}

        async def _fails(**kwargs: object) -> dict[str, bool]:
            raise RuntimeError("intentional widget-test failure")

        provider.registry.register("widget_ok", _succeeds)
        provider.registry.register("widget_boom", _fails)
        pool.refresh_handlers()

        await provider.queue.enqueue(JobProtocol(id="", name="widget_ok"))
        await provider.queue.enqueue(JobProtocol(id="", name="widget_boom"))

        for _ in range(100):
            stats = pool.get_pool_stats()
            if stats["total_jobs_processed"] >= 2:
                break
            await asyncio.sleep(0.1)

        stats = pool.get_pool_stats()
        assert stats["total_jobs_succeeded"] == 1, stats
        assert stats["total_jobs_failed"] == 1, stats
        assert stats["average_processing_time"] > 0, stats

        summary = (
            await TasksSummaryWidgetHandler(
                queue_provider=provider.queue, pool_provider=pool
            ).get_data(WidgetParams())
        ).unwrap()
        values = {stat.label: stat.value for stat in summary.stats}
        assert values["Pending"] == "0", values
        assert values["Completed"] == "1", values
        assert values["Failed"] == "1", values

        duration = (
            await AvgDurationWidgetHandler(pool_provider=pool).get_data(WidgetParams())
        ).unwrap()
        measured = {stat.label: stat.value for stat in duration.stats}
        assert measured["Avg"].endswith("ms"), measured
        assert measured["Avg"] != "0.0ms", measured
    finally:
        await pool.stop()
