"""Tests for BackgroundTaskManager (QK-006)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from quadkit.tasks.background_task_manager import BackgroundTaskManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _noop() -> str:
    """Complete immediately."""
    return "done"


async def _ignore_cancel(release: asyncio.Event) -> None:
    """Wait until released, even after cancellation is requested."""
    try:
        await release.wait()
    except asyncio.CancelledError:
        await release.wait()


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
# Done-callback cleanup and safe exception logging
# ---------------------------------------------------------------------------


class TestBackgroundTaskManagerCallbacks:
    """Task callbacks clean up without exposing task names or errors."""

    @pytest.mark.asyncio
    async def test_unnamed_task_completion_raises_no_exception_handler_call(
        self,
    ) -> None:
        """Tracked unnamed tasks must not trigger the loop exception handler."""
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
    async def test_completed_task_is_removed_from_tracking(self) -> None:
        """Completed named tasks are removed from the tracked set."""
        mgr = BackgroundTaskManager()
        task = mgr.track_named("my-job", _noop())
        await task
        await asyncio.sleep(0)
        assert task not in mgr._tasks
        assert mgr.pending_count == 0

    @pytest.mark.asyncio
    async def test_task_failure_logs_type_only_without_task_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exception text and task names must not enter worker logs."""
        import quadkit.tasks.background_task_manager as manager_module

        logger = MagicMock()
        monkeypatch.setattr(manager_module, "logger", logger)
        private_task_name = "private-user-task-42"
        private_error = "private /srv/app/user-42 request=secret"

        async def _fail() -> None:
            raise ValueError(private_error)

        task = BackgroundTaskManager().track_named(private_task_name, _fail())
        with pytest.raises(ValueError):
            await task
        await asyncio.sleep(0)  # run the task's done callback

        logger.error.assert_called_once_with(
            "background_task_manager.task_failed",
            error_type="ValueError",
        )
        logged = repr(logger.error.call_args)
        assert private_task_name not in logged
        assert private_error not in logged
        assert "/srv/app" not in logged
        assert "user-42" not in logged


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
        release = asyncio.Event()
        task = mgr.track(_ignore_cancel(release))
        await asyncio.sleep(0)

        started = asyncio.get_event_loop().time()
        await mgr.shutdown(timeout=0.1)
        elapsed = asyncio.get_event_loop().time() - started

        # Allow 0.5 s of overhead for the test runner.
        assert elapsed < 0.6, f"shutdown took {elapsed:.2f}s — expected ≤ 0.6s"
        release.set()
        await task

    @pytest.mark.asyncio
    async def test_shutdown_timeout_warning_omits_task_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Timed-out task logs include a count but never the task name."""
        import quadkit.tasks.background_task_manager as manager_module

        logger = MagicMock()
        monkeypatch.setattr(manager_module, "logger", logger)
        mgr = BackgroundTaskManager()
        private_task_name = "private-stubborn-task-42"
        release = asyncio.Event()
        task = mgr.track_named(private_task_name, _ignore_cancel(release))
        await asyncio.sleep(0)  # let the task start

        await mgr.shutdown(timeout=0.05)

        logger.warning.assert_called_once_with(
            "background_task_manager.shutdown_timeout",
            timed_out=1,
            timeout=0.05,
        )
        assert private_task_name not in repr(logger.warning.call_args)
        release.set()
        await task
