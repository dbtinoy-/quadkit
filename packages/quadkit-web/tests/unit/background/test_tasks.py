"""Tests for background/tasks.py — BackgroundTasks, StarletteBackgroundTaskRunner, etc."""

from __future__ import annotations

import contextvars
from typing import Any

import pytest

import quadkit.web.background as background_module
from quadkit.web.background.tasks import (
    BackgroundTasks,
    BackgroundTaskScope,
    StarletteBackgroundTaskRunner,
)


def test_background_module_does_not_export_task_queue_runner() -> None:
    assert not hasattr(background_module, "TaskQueueBackgroundTaskRunner")


class TestBackgroundTasks:
    def test_initial_state(self) -> None:
        bt = BackgroundTasks()
        assert len(bt) == 0
        assert not bool(bt)

    def test_add_task(self) -> None:
        bt = BackgroundTasks()
        bt.add(lambda: None)
        assert len(bt) == 1
        assert bool(bt)

    def test_add_multiple_tasks(self) -> None:
        bt = BackgroundTasks()
        bt.add(lambda: None)
        bt.add(lambda: None, "arg1", key="val")
        assert len(bt) == 2

    def test_len_and_bool(self) -> None:
        bt = BackgroundTasks()
        assert len(bt) == 0
        assert not bt
        bt.add(lambda: None)
        assert len(bt) == 1
        assert bt


class TestStarletteBackgroundTaskRunner:
    def test_add_task_delegates_to_starlette(self) -> None:
        runner = StarletteBackgroundTaskRunner()
        called = []
        runner.add_task(called.append, "item")
        starlette_bt = runner._to_starlette()
        assert starlette_bt is not None

    def test_to_starlette_returns_background_tasks(self) -> None:
        runner = StarletteBackgroundTaskRunner()
        from starlette.background import BackgroundTasks as StarletteBackgroundTasks

        assert isinstance(runner._to_starlette(), StarletteBackgroundTasks)


class TestBackgroundTaskScope:
    def test_initial_state(self) -> None:
        scope = BackgroundTaskScope()
        assert isinstance(scope.tasks, BackgroundTasks)
        assert len(scope.tasks) == 0

    def test_add_task(self) -> None:
        scope = BackgroundTaskScope()
        scope.add(lambda: None)
        assert len(scope.tasks) == 1

    def test_tasks_property_returns_same_instance(self) -> None:
        scope = BackgroundTaskScope()
        assert scope.tasks is scope.tasks


# ---------------------------------------------------------------------------
# Context-propagation tests (TDD — these tests define the required behaviour)
# ---------------------------------------------------------------------------


class TestBackgroundTasksContextPropagation:
    """BackgroundTasks.add() must snapshot context; _execute_all() must restore it."""

    @pytest.mark.asyncio
    async def test_execute_all_propagates_context_to_async_task(self) -> None:
        """Async tasks added to BackgroundTasks see the context from add() time."""
        var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
            "bg_test_var", default=None
        )
        captured: list[str | None] = []

        var.set("at_queue_time")
        bt = BackgroundTasks()

        async def async_reader() -> None:
            captured.append(var.get())

        bt.add(async_reader)

        # Mutate context AFTER queuing — task must still see the earlier value.
        var.set("after_queue")

        await bt._execute_all()

        assert captured == ["at_queue_time"]

    @pytest.mark.asyncio
    async def test_execute_all_propagates_context_to_sync_task(self) -> None:
        """Sync tasks added to BackgroundTasks see the context from add() time."""
        var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
            "bg_sync_test_var", default=None
        )
        captured: list[str | None] = []

        var.set("sync_queue_value")
        bt = BackgroundTasks()

        def sync_reader() -> None:
            captured.append(var.get())

        bt.add(sync_reader)
        var.set("sync_after_queue")

        await bt._execute_all()

        assert captured == ["sync_queue_value"]


class TestStarletteRunnerContextPropagation:
    """StarletteBackgroundTaskRunner must capture context at add_task() time."""

    @pytest.mark.asyncio
    async def test_context_propagated_to_starlette_task(self) -> None:
        """Task sees context vars as they were when add_task() was called."""
        var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
            "starlette_test_var", default=None
        )
        captured: list[str | None] = []

        var.set("at_add_task_time")
        runner = StarletteBackgroundTaskRunner()

        async def reader() -> None:
            captured.append(var.get())

        runner.add_task(reader)

        # Mutate context after queuing.
        var.set("after_add_task")

        # Execute all queued Starlette background tasks directly.
        await runner._to_starlette()()

        assert captured == ["at_add_task_time"]

    @pytest.mark.asyncio
    async def test_context_propagated_to_sync_starlette_task(self) -> None:
        """Sync tasks also see context from add_task() time."""
        var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
            "starlette_sync_var", default=None
        )
        captured: list[str | None] = []

        var.set("sync_at_add")
        runner = StarletteBackgroundTaskRunner()

        def sync_reader() -> None:
            captured.append(var.get())

        runner.add_task(sync_reader)
        var.set("sync_after_add")

        await runner._to_starlette()()

        assert captured == ["sync_at_add"]


# ---------------------------------------------------------------------------
# Regression: sync Starlette background tasks must NOT be wrapped async
# ---------------------------------------------------------------------------


class TestStarletteSyncTaskExecutionPath:
    """Sync callables must remain sync so Starlette uses its threadpool offload."""

    def test_sync_task_produces_sync_starlette_task(self) -> None:
        """A sync callable must produce a non-async Starlette BackgroundTask.

        When a sync func is wrapped in an async closure and handed to Starlette,
        Starlette sets ``is_async=True`` and awaits it directly on the event loop
        instead of dispatching it to the threadpool via ``run_in_executor``.
        This regression test guards against that path.
        """
        runner = StarletteBackgroundTaskRunner()

        def sync_fn() -> None:
            pass

        runner.add_task(sync_fn)
        starlette_bt = runner._to_starlette()
        task = starlette_bt.tasks[0]
        assert not task.is_async, (
            "Sync callable was wrapped in an async closure — "
            "Starlette will not offload it to the threadpool"
        )

    def test_async_task_produces_async_starlette_task(self) -> None:
        """An async callable must still produce an async Starlette BackgroundTask."""
        runner = StarletteBackgroundTaskRunner()

        async def async_fn() -> None:
            pass

        runner.add_task(async_fn)
        starlette_bt = runner._to_starlette()
        task = starlette_bt.tasks[0]
        assert task.is_async, "Async callable must produce an async Starlette task"


# ---------------------------------------------------------------------------
# Regression: async callable objects must be detected and awaited correctly
# ---------------------------------------------------------------------------


class _AsyncCallableObj:
    """Callable class with async __call__ — asyncio.iscoroutinefunction returns False."""

    def __init__(self, sink: list[str], value: str = "called") -> None:
        self._sink = sink
        self._value = value

    async def __call__(self, *_args: Any, **_kwargs: Any) -> None:
        self._sink.append(self._value)


class TestAsyncCallableObjectDetection:
    """Async callable objects (async def __call__) must be awaited, not called raw."""

    @pytest.mark.asyncio
    async def test_background_tasks_execute_all_awaits_async_callable_obj(
        self,
    ) -> None:
        """BackgroundTasks._execute_all() must await async callable objects."""
        sink: list[str] = []
        obj = _AsyncCallableObj(sink, "bg_async_obj")

        bt = BackgroundTasks()
        bt.add(obj)
        await bt._execute_all()

        assert sink == ["bg_async_obj"], (
            "_execute_all() did not await async callable object"
        )

    @pytest.mark.asyncio
    async def test_starlette_runner_async_callable_obj_registered_as_async(
        self,
    ) -> None:
        """StarletteBackgroundTaskRunner must register an async callable object as async."""
        sink: list[str] = []
        obj = _AsyncCallableObj(sink, "starlette_async_obj")

        runner = StarletteBackgroundTaskRunner()
        runner.add_task(obj)

        starlette_bt = runner._to_starlette()
        task = starlette_bt.tasks[0]
        assert task.is_async, (
            "Async callable object must produce an async Starlette task"
        )

    @pytest.mark.asyncio
    async def test_starlette_runner_async_callable_obj_executes(self) -> None:
        """StarletteBackgroundTaskRunner actually runs an async callable object."""
        sink: list[str] = []
        obj = _AsyncCallableObj(sink, "starlette_exec_obj")

        runner = StarletteBackgroundTaskRunner()
        runner.add_task(obj)

        await runner._to_starlette()()

        assert sink == ["starlette_exec_obj"], (
            "Async callable object was not executed correctly via Starlette runner"
        )
