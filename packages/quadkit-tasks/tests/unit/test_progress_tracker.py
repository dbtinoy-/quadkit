"""Tests for ProgressTrackerProtocol, ProgressSnapshot, ProgressStatus,
and InMemoryProgressTracker.

Coverage targets:
- ProgressSnapshot data model and .percent property
- ProgressStatus enum values and str behaviour
- InMemoryProgressTracker: update / complete / fail / get
- InMemoryProgressTracker: subscribe live streaming
- InMemoryProgressTracker: subscribe after terminal state
- InMemoryProgressTracker: multiple concurrent subscribers
- InMemoryProgressTracker: subscriber cleanup on early break
- Protocol conformance via isinstance check
"""

from __future__ import annotations

import asyncio

import pytest

from quadkit.contracts.infra.tasks.progress import (
    ProgressSnapshot,
    ProgressStatus,
    ProgressTrackerProtocol,
)
from quadkit.tasks.progress import InMemoryProgressTracker

# ---------------------------------------------------------------------------
# ProgressStatus
# ---------------------------------------------------------------------------


class TestProgressStatus:
    def test_values_are_lowercase_strings(self) -> None:
        assert ProgressStatus.PENDING == "pending"
        assert ProgressStatus.RUNNING == "running"
        assert ProgressStatus.COMPLETE == "complete"
        assert ProgressStatus.FAILED == "failed"

    def test_is_str_subclass(self) -> None:
        assert isinstance(ProgressStatus.RUNNING, str)

    def test_terminal_states(self) -> None:
        terminal = {ProgressStatus.COMPLETE, ProgressStatus.FAILED}
        assert ProgressStatus.COMPLETE in terminal
        assert ProgressStatus.FAILED in terminal
        assert ProgressStatus.PENDING not in terminal
        assert ProgressStatus.RUNNING not in terminal


# ---------------------------------------------------------------------------
# ProgressSnapshot
# ---------------------------------------------------------------------------


class TestProgressSnapshot:
    def test_percent_normal(self) -> None:
        snap = ProgressSnapshot(
            task_id="t1", current=25, total=100, status=ProgressStatus.RUNNING
        )
        assert snap.percent == 25.0

    def test_percent_zero_total_returns_zero(self) -> None:
        snap = ProgressSnapshot(
            task_id="t1", current=0, total=0, status=ProgressStatus.PENDING
        )
        assert snap.percent == 0.0

    def test_percent_capped_at_100(self) -> None:
        snap = ProgressSnapshot(
            task_id="t1", current=110, total=100, status=ProgressStatus.RUNNING
        )
        assert snap.percent == 100.0

    def test_percent_complete(self) -> None:
        snap = ProgressSnapshot(
            task_id="t1", current=50, total=50, status=ProgressStatus.COMPLETE
        )
        assert snap.percent == 100.0

    def test_default_message_and_error_are_empty(self) -> None:
        snap = ProgressSnapshot(
            task_id="t1", current=0, total=10, status=ProgressStatus.PENDING
        )
        assert snap.message == ""
        assert snap.error == ""
        assert snap.metadata == {}

    def test_frozen(self) -> None:
        snap = ProgressSnapshot(
            task_id="t1", current=1, total=10, status=ProgressStatus.RUNNING
        )
        with pytest.raises((AttributeError, TypeError)):
            snap.current = 2  # type: ignore[misc]

    def test_error_field_populated_on_failed(self) -> None:
        snap = ProgressSnapshot(
            task_id="t1",
            current=3,
            total=10,
            status=ProgressStatus.FAILED,
            error="connection lost",
        )
        assert snap.error == "connection lost"


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_in_memory_tracker_is_protocol(self) -> None:
        tracker = InMemoryProgressTracker()
        assert isinstance(tracker, ProgressTrackerProtocol)


# ---------------------------------------------------------------------------
# InMemoryProgressTracker — update / get / complete / fail
# ---------------------------------------------------------------------------


class TestInMemoryProgressTrackerBasics:
    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown_task(self) -> None:
        tracker = InMemoryProgressTracker()
        result = await tracker.get("does-not-exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_stores_snapshot(self) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.update("t1", 3, 10, "step 3")
        snap = await tracker.get("t1")
        assert snap is not None
        assert snap.task_id == "t1"
        assert snap.current == 3
        assert snap.total == 10
        assert snap.message == "step 3"
        assert snap.status == ProgressStatus.RUNNING

    @pytest.mark.asyncio
    async def test_update_overwrites_previous(self) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.update("t1", 1, 5)
        await tracker.update("t1", 3, 5, "halfway-ish")
        snap = await tracker.get("t1")
        assert snap is not None
        assert snap.current == 3

    @pytest.mark.asyncio
    async def test_complete_sets_complete_status(self) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.update("t1", 5, 5)
        await tracker.complete("t1", "all done")
        snap = await tracker.get("t1")
        assert snap is not None
        assert snap.status == ProgressStatus.COMPLETE
        assert snap.message == "all done"

    @pytest.mark.asyncio
    async def test_complete_preserves_copied_metadata(self) -> None:
        """Completion hints are retained without sharing caller-owned state."""
        tracker = InMemoryProgressTracker()
        metadata: dict[str, object] = {"toast_type": "success", "refresh": True}
        await tracker.complete("t1", "all done", metadata)
        metadata["refresh"] = False

        snap = await tracker.get("t1")
        assert snap is not None
        assert snap.metadata == {"toast_type": "success", "refresh": True}

    @pytest.mark.asyncio
    async def test_complete_preserves_total(self) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.update("t1", 7, 10)
        await tracker.complete("t1")
        snap = await tracker.get("t1")
        assert snap is not None
        assert snap.total == 10
        assert snap.current == 10

    @pytest.mark.asyncio
    async def test_complete_on_fresh_task_uses_zero_total(self) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.complete("new-task", "done")
        snap = await tracker.get("new-task")
        assert snap is not None
        assert snap.total == 0
        assert snap.current == 0

    @pytest.mark.asyncio
    async def test_fail_sets_failed_status(self) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.update("t1", 2, 10)
        await tracker.fail("t1", "disk full")
        snap = await tracker.get("t1")
        assert snap is not None
        assert snap.status == ProgressStatus.FAILED
        assert snap.error == "disk full"

    @pytest.mark.asyncio
    async def test_fail_preserves_metadata(self) -> None:
        """Failure hints remain available to progress consumers."""
        tracker = InMemoryProgressTracker()
        await tracker.fail("t1", "disk full", {"retryable": False})

        snap = await tracker.get("t1")
        assert snap is not None
        assert snap.metadata == {"retryable": False}

    @pytest.mark.asyncio
    async def test_fail_preserves_current_and_total(self) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.update("t1", 4, 10)
        await tracker.fail("t1", "oops")
        snap = await tracker.get("t1")
        assert snap is not None
        assert snap.current == 4
        assert snap.total == 10

    @pytest.mark.asyncio
    async def test_percent_correct_after_update(self) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.update("t1", 1, 4)
        snap = await tracker.get("t1")
        assert snap is not None
        assert snap.percent == 25.0


# ---------------------------------------------------------------------------
# InMemoryProgressTracker — subscribe live streaming
# ---------------------------------------------------------------------------


class TestInMemoryProgressTrackerSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_receives_update_and_complete(self) -> None:
        tracker = InMemoryProgressTracker()
        received: list[ProgressSnapshot] = []

        async def consumer() -> None:
            async for snap in tracker.subscribe("t1"):
                received.append(snap)

        consumer_task = asyncio.create_task(consumer())
        # Yield control so the consumer coroutine reaches its first `await`.
        await asyncio.sleep(0)

        await tracker.update("t1", 1, 3, "one")
        await tracker.update("t1", 2, 3, "two")
        await tracker.complete("t1", "done")

        await consumer_task

        assert len(received) == 3
        assert received[0].current == 1
        assert received[1].current == 2
        assert received[2].status == ProgressStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_subscribe_stops_after_fail(self) -> None:
        tracker = InMemoryProgressTracker()
        received: list[ProgressSnapshot] = []

        async def consumer() -> None:
            async for snap in tracker.subscribe("t1"):
                received.append(snap)

        consumer_task = asyncio.create_task(consumer())
        await asyncio.sleep(0)

        await tracker.update("t1", 1, 5)
        await tracker.fail("t1", "bad input")

        await consumer_task

        assert len(received) == 2
        assert received[-1].status == ProgressStatus.FAILED
        assert received[-1].error == "bad input"

    @pytest.mark.asyncio
    async def test_subscribe_after_complete_yields_terminal_snapshot_once(
        self,
    ) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.update("t1", 5, 5)
        await tracker.complete("t1", "finished")

        received: list[ProgressSnapshot] = []
        async for snap in tracker.subscribe("t1"):
            received.append(snap)

        assert len(received) == 1
        assert received[0].status == ProgressStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_subscribe_after_fail_yields_terminal_snapshot_once(
        self,
    ) -> None:
        tracker = InMemoryProgressTracker()
        await tracker.update("t1", 2, 10)
        await tracker.fail("t1", "crash")

        received: list[ProgressSnapshot] = []
        async for snap in tracker.subscribe("t1"):
            received.append(snap)

        assert len(received) == 1
        assert received[0].status == ProgressStatus.FAILED

    @pytest.mark.asyncio
    async def test_multiple_concurrent_subscribers(self) -> None:
        tracker = InMemoryProgressTracker()
        received_a: list[ProgressSnapshot] = []
        received_b: list[ProgressSnapshot] = []

        async def consumer_a() -> None:
            async for snap in tracker.subscribe("t1"):
                received_a.append(snap)

        async def consumer_b() -> None:
            async for snap in tracker.subscribe("t1"):
                received_b.append(snap)

        task_a = asyncio.create_task(consumer_a())
        task_b = asyncio.create_task(consumer_b())
        await asyncio.sleep(0)

        await tracker.update("t1", 1, 2)
        await tracker.complete("t1")

        await asyncio.gather(task_a, task_b)

        assert len(received_a) == 2
        assert len(received_b) == 2

    @pytest.mark.asyncio
    async def test_subscriber_queue_cleaned_up_after_completion(self) -> None:
        tracker = InMemoryProgressTracker()

        async def consumer() -> None:
            async for _ in tracker.subscribe("t1"):
                pass

        t = asyncio.create_task(consumer())
        await asyncio.sleep(0)
        await tracker.complete("t1")
        await t

        # After the iterator closes, the subscriber list should be empty.
        assert "t1" not in tracker._subscribers

    @pytest.mark.asyncio
    async def test_subscriber_queue_cleaned_up_on_early_break(self) -> None:
        tracker = InMemoryProgressTracker()

        async def consumer() -> None:
            async for snap in tracker.subscribe("t1"):
                if snap.current >= 1:
                    break  # exit early

        t = asyncio.create_task(consumer())
        await asyncio.sleep(0)
        await tracker.update("t1", 1, 5)
        await t

        # asyncio schedules the async generator's aclose() finalizer to run in
        # the next event-loop tick, not synchronously inside the break.  Yield
        # once so the finalizer has a chance to execute the finally block.
        await asyncio.sleep(0)

        # The finally block should have removed the queue entry.
        assert "t1" not in tracker._subscribers
