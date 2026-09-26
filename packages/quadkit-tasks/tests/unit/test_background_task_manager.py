"""Tests for BackgroundTaskManager (QK-006)."""

from __future__ import annotations

import asyncio

import pytest

from quadkit.tasks.background_task_manager import BackgroundTaskManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _noop() -> str:
    """Complete immediately."""
    return "done"


async def _long_running(duration: float = 10.0) -> None:
    """Sleep for a long time — simulates a task that ignores cancellation."""
    try:
        await asyncio.sleep(duration)
    except asyncio.CancelledError:
        # silently swallow cancel for the timeout test
        await asyncio.sleep(duration)


# ---------------------------------------------------------------------------
# Track / pending_count
# ---------------------------------------------------------------------------


class TestBackgroundTaskManagerTracking:
    @pytest.mark.asyncio
    async def test_track_returns_task(self) -> None:
        mgr = BackgroundTaskManager()
        task = mgr.track(_noop())
        assert isinstance(task, asyncio.Task)
        await task  # allow completion

    @pytest.mark.asyncio
    async def test_track_increments_pending_count(self) -> None:
        mgr = BackgroundTaskManager()
        evt = asyncio.Event()

        async def _wait() -> None:
            await evt.wait()

        mgr.track(_wait())
        assert mgr.pending_count == 1
        evt.set()
        await asyncio.sleep(0)  # let the task finish

    @pytest.mark.asyncio
    async def test_track_named_uses_name(self) -> None:
        mgr = BackgroundTaskManager()
        task = mgr.track_named("my-job", _noop())
        assert task.get_name() == "my-job"
        await task

    @pytest.mark.asyncio
    async def test_pending_count_decrements_after_completion(self) -> None:
        mgr = BackgroundTaskManager()
        task = mgr.track(_noop())
        await task
        # give the done_callback a chance to run
        await asyncio.sleep(0)
        assert mgr.pending_count == 0

    @pytest.mark.asyncio
    async def test_successful_task_does_not_linger(self) -> None:
        mgr = BackgroundTaskManager()
        task = mgr.track(_noop())
        await task
        await asyncio.sleep(0)
        assert mgr.pending_count == 0


# ---------------------------------------------------------------------------
# Done-callback cleanup — _names (regression: KeyError for unnamed tasks)
# ---------------------------------------------------------------------------


class TestBackgroundTaskManagerNamesCleanup:
    """Regression tests for _names cleanup on task completion."""

    @pytest.mark.asyncio
    async def test_unnamed_task_completion_raises_no_exception_handler_call(
        self,
    ) -> None:
        """Tracked unnamed tasks must not trigger the loop exception handler.

        Regression: the ``self._names.pop`` done-callback raised ``KeyError``
        for every task created via ``track()`` because those tasks are never
        inserted into ``self._names``, and ``asyncio`` reports exceptions
        raised by done-callbacks to the loop's exception handler.
        """
        loop = asyncio.get_running_loop()
        handler_calls: list[BaseException | None] = []
        original_handler = loop.get_exception_handler()
        loop.set_exception_handler(
            lambda _loop, context: handler_calls.append(context.get("exception"))
        )
        try:
            mgr = BackgroundTaskManager()
            task = mgr.track(_noop())
            await task
            await asyncio.sleep(0)  # give the done callbacks a chance to run
        finally:
            loop.set_exception_handler(original_handler)

        assert handler_calls == []

    @pytest.mark.asyncio
    async def test_unnamed_task_never_enters_names(self) -> None:
        """``track()`` tasks stay out of ``_names`` before and after."""
        mgr = BackgroundTaskManager()
        task = mgr.track(_noop())
        assert task not in mgr._names
        await task
        await asyncio.sleep(0)
        assert task not in mgr._names

    @pytest.mark.asyncio
    async def test_named_task_name_removed_on_completion(self) -> None:
        """``track_named()`` entries are removed from ``_names`` on done."""
        mgr = BackgroundTaskManager()
        task = mgr.track_named("my-job", _noop())
        assert mgr._names[task] == "my-job"
        await task
        await asyncio.sleep(0)
        assert task not in mgr._names


# ---------------------------------------------------------------------------
# Shutdown — happy path
# ---------------------------------------------------------------------------


class TestBackgroundTaskManagerShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_with_no_pending_tasks(self) -> None:
        mgr = BackgroundTaskManager()
        # Should complete immediately without raising
        await mgr.shutdown(timeout=1.0)

    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_tasks(self) -> None:
        mgr = BackgroundTaskManager()
        task = mgr.track(asyncio.sleep(60))
        await mgr.shutdown(timeout=2.0)
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_pending_count_zero_after_shutdown(self) -> None:
        mgr = BackgroundTaskManager()
        mgr.track(asyncio.sleep(60))
        await mgr.shutdown(timeout=2.0)
        assert mgr.pending_count == 0

    @pytest.mark.asyncio
    async def test_shutdown_multiple_tasks(self) -> None:
        mgr = BackgroundTaskManager()
        tasks = [mgr.track(asyncio.sleep(60)) for _ in range(5)]
        await mgr.shutdown(timeout=2.0)
        assert all(t.cancelled() for t in tasks)


# ---------------------------------------------------------------------------
# Shutdown — timeout path
# ---------------------------------------------------------------------------


class TestBackgroundTaskManagerShutdownTimeout:
    @pytest.mark.asyncio
    async def test_shutdown_returns_within_timeout_even_if_task_ignores_cancel(
        self,
    ) -> None:
        """shutdown() must not block beyond timeout even for stubborn tasks."""
        mgr = BackgroundTaskManager()
        # _long_running swallows CancelledError — simulates worst-case
        mgr.track(_long_running(duration=60.0))

        started = asyncio.get_event_loop().time()
        await mgr.shutdown(timeout=0.1)
        elapsed = asyncio.get_event_loop().time() - started

        # Allow 0.5 s of overhead for the test runner
        assert elapsed < 0.6, f"shutdown took {elapsed:.2f}s — expected ≤ 0.6s"

    @pytest.mark.asyncio
    async def test_shutdown_logs_timed_out_named_task(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Named tasks that time out should emit a timeout warning in logs."""
        mgr = BackgroundTaskManager()
        # Let the task start before we try to shut it down
        task = mgr.track_named("stubborn-task", _long_running(duration=60.0))
        await asyncio.sleep(0)  # let the event loop schedule the task
        await asyncio.sleep(0)  # let it enter its first sleep

        await mgr.shutdown(timeout=0.05)

        captured = capsys.readouterr()
        output = captured.out + captured.err
        # Either "stubborn-task" is mentioned OR the log records that something timed out
        assert "stubborn-task" in output or "shutdown_timeout" in output or "timed_out" in output
        _ = task  # suppress unused-variable warnings
