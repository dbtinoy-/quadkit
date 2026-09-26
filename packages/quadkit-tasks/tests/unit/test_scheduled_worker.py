"""Tests for ScheduledWorker (QK-005)."""

from __future__ import annotations

import asyncio

import pytest

from quadkit.tasks.background_task_manager import BackgroundTaskManager
from quadkit.tasks.scheduled_worker import OnErrorPolicy, ScheduledWorker

# ---------------------------------------------------------------------------
# Concrete workers for testing
# ---------------------------------------------------------------------------


class _CountingWorker(ScheduledWorker):
    """Increments a counter on every cycle."""

    interval_seconds = 0.1
    initial_delay_seconds = 0.0

    def __init__(self, task_manager: BackgroundTaskManager, **kwargs: object) -> None:
        super().__init__(task_manager, **kwargs)
        self.cycle_count = 0

    async def run_cycle(self) -> None:
        self.cycle_count += 1


class _FailingWorker(ScheduledWorker):
    """Raises on every cycle."""

    interval_seconds = 0.05
    initial_delay_seconds = 0.0

    def __init__(
        self,
        task_manager: BackgroundTaskManager,
        policy: OnErrorPolicy = OnErrorPolicy.LOG_AND_CONTINUE,
    ) -> None:
        super().__init__(task_manager, on_error_policy=policy)
        self.cycle_count = 0

    async def run_cycle(self) -> None:
        self.cycle_count += 1
        raise ValueError("intentional test error")


class _SlowCycleWorker(ScheduledWorker):
    """Each cycle takes a long time — used to test stop() mid-cycle."""

    interval_seconds = 0.1
    initial_delay_seconds = 0.0

    def __init__(self, task_manager: BackgroundTaskManager) -> None:
        super().__init__(task_manager)
        self.started = False

    async def run_cycle(self) -> None:
        self.started = True
        await asyncio.sleep(60.0)  # blocks until cancelled


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager() -> BackgroundTaskManager:
    return BackgroundTaskManager()


# ---------------------------------------------------------------------------
# Basic start / run / stop
# ---------------------------------------------------------------------------


class TestScheduledWorkerLifecycle:
    """Lifecycle coverage for scheduled worker execution."""

    @pytest.mark.asyncio
    async def test_worker_runs_at_least_two_cycles(self) -> None:
        """Worker must execute run_cycle() at least twice in under 1 s."""
        mgr = _make_manager()
        worker = _CountingWorker(mgr)

        await worker.start()
        await asyncio.sleep(0.35)  # 0.1 s interval → ≥ 2 full cycles
        await worker.stop()

        assert worker.cycle_count >= 2, f"Expected ≥ 2 cycles, got {worker.cycle_count}"

    @pytest.mark.asyncio
    async def test_worker_stops_cleanly(self) -> None:
        """stop() should complete and the background task should not be running."""
        mgr = _make_manager()
        worker = _CountingWorker(mgr)

        await worker.start()
        await asyncio.sleep(0.05)
        await worker.stop()

        assert worker._task is None or worker._task.done()

    @pytest.mark.asyncio
    async def test_start_twice_is_noop(self) -> None:
        """Calling start() on a running worker logs a warning and does nothing."""
        mgr = _make_manager()
        worker = _CountingWorker(mgr)

        await worker.start()
        task_before = worker._task
        await worker.start()  # second call — should be ignored
        assert worker._task is task_before  # same task object
        await worker.stop()

    @pytest.mark.asyncio
    async def test_no_zombie_tasks_after_stop(self) -> None:
        """BackgroundTaskManager should have 0 pending tasks after stop()."""
        mgr = _make_manager()
        worker = _CountingWorker(mgr)

        await worker.start()
        await asyncio.sleep(0.05)
        await worker.stop()
        await asyncio.sleep(0)  # flush callbacks

        assert mgr.pending_count == 0


# ---------------------------------------------------------------------------
# Error policies
# ---------------------------------------------------------------------------


class TestScheduledWorkerErrorPolicies:
    """Error-policy coverage for scheduled worker execution."""

    @pytest.mark.asyncio
    async def test_log_and_continue_survives_errors(self) -> None:
        """Worker with LOG_AND_CONTINUE keeps running after cycle errors."""
        mgr = _make_manager()
        worker = _FailingWorker(mgr, policy=OnErrorPolicy.LOG_AND_CONTINUE)

        await worker.start()
        for _ in range(50):
            if worker.cycle_count >= 2:
                break
            await asyncio.sleep(0.02)
        await worker.stop()

        # Should have attempted at least 2 cycles despite errors
        assert worker.cycle_count >= 2, f"Expected ≥ 2 cycles, got {worker.cycle_count}"

    @pytest.mark.asyncio
    async def test_stop_policy_halts_after_first_failure(self) -> None:
        """Worker with STOP policy stops itself after one failing cycle."""
        mgr = _make_manager()
        worker = _FailingWorker(mgr, policy=OnErrorPolicy.STOP)

        await worker.start()
        # Give the loop time to run the first cycle and halt
        await asyncio.sleep(0.3)

        # The task should have completed on its own (policy=STOP)
        assert worker._task is not None
        assert worker._task.done(), "Task should have stopped after first failure"
        assert worker.cycle_count == 1, (
            f"Expected exactly 1 cycle, got {worker.cycle_count}"
        )

    @pytest.mark.asyncio
    async def test_backoff_policy_continues_after_error(self) -> None:
        """Worker with BACKOFF policy keeps running (with increased sleep)."""
        mgr = _make_manager()
        worker = _FailingWorker(mgr, policy=OnErrorPolicy.BACKOFF)

        await worker.start()
        await asyncio.sleep(0.3)
        await worker.stop()

        # Should have run at least one cycle
        assert worker.cycle_count >= 1


# ---------------------------------------------------------------------------
# stop() mid-cycle
# ---------------------------------------------------------------------------


class TestScheduledWorkerStopMidCycle:
    """Stop behavior coverage while a cycle is in flight."""

    @pytest.mark.asyncio
    async def test_stop_mid_cycle_no_zombie_tasks(self) -> None:
        """stop() during a long cycle leaves no zombie tasks."""
        mgr = _make_manager()
        worker = _SlowCycleWorker(mgr)

        await worker.start()
        # Wait until the cycle has started
        for _ in range(20):
            if worker.started:
                break
            await asyncio.sleep(0.02)

        assert worker.started, "Cycle never started"

        await worker.stop()
        await asyncio.sleep(0)  # flush done callbacks

        assert mgr.pending_count == 0, (
            f"Expected 0 pending tasks, got {mgr.pending_count}"
        )

    @pytest.mark.asyncio
    async def test_stop_completes_in_reasonable_time(self) -> None:
        """stop() with a mid-cycle worker should return within grace + overhead."""
        mgr = _make_manager()
        worker = _SlowCycleWorker(mgr)

        await worker.start()
        for _ in range(20):
            if worker.started:
                break
            await asyncio.sleep(0.02)

        started = asyncio.get_event_loop().time()
        await worker.stop(grace_seconds=0.1)
        elapsed = asyncio.get_event_loop().time() - started

        # 0.1 s grace + overhead — should complete well under 2 s
        assert elapsed < 2.0, f"stop() took {elapsed:.2f}s — too slow"


# ---------------------------------------------------------------------------
# OnErrorPolicy values
# ---------------------------------------------------------------------------


class TestOnErrorPolicy:
    """Enum coverage for scheduled worker error policies."""

    def test_policy_values_are_strings(self) -> None:
        """Keep the policy values aligned with their wire format."""
        assert OnErrorPolicy.LOG_AND_CONTINUE.value == "LOG_AND_CONTINUE"
        assert OnErrorPolicy.BACKOFF.value == "BACKOFF"
        assert OnErrorPolicy.STOP.value == "STOP"

    def test_policy_is_str_subclass(self) -> None:
        """Make sure the policy remains string-compatible."""
        assert isinstance(OnErrorPolicy.LOG_AND_CONTINUE, str)
        assert isinstance(OnErrorPolicy.STOP, str)

    def test_policy_identity(self) -> None:
        """Preserve enum identity semantics for policy lookups."""
        assert OnErrorPolicy.LOG_AND_CONTINUE is OnErrorPolicy("LOG_AND_CONTINUE")
        assert OnErrorPolicy.STOP is OnErrorPolicy("STOP")
