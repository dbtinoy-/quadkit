"""Tests for the in-memory outbox and relay (memory/outbox.py)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from quadkit.contracts.domain.events import DomainEvent
from quadkit.testing.memory.event_bus import InMemoryEventBus
from quadkit.testing.memory.outbox import (
    InMemoryOutbox,
    OutboxEntry,
    OutboxRelay,
    OutboxStatus,
)


class UserCreated(DomainEvent):
    user_id: str = ""


class OrderShipped(DomainEvent):
    order_id: str = ""


@pytest.fixture
def outbox() -> InMemoryOutbox:
    return InMemoryOutbox()


class TestInMemoryOutbox:
    @pytest.mark.asyncio
    async def test_store_event_returns_pending_entry(self, outbox) -> None:
        entry = await outbox.store_event(UserCreated(user_id="u1"))
        assert isinstance(entry, OutboxEntry)
        assert entry.status is OutboxStatus.PENDING
        assert entry.event.user_id == "u1"
        assert entry.published_at is None
        assert entry.error is None

    @pytest.mark.asyncio
    async def test_get_pending_returns_fifo_and_respects_limit(self, outbox) -> None:
        first = await outbox.store_event(UserCreated(user_id="1"))
        second = await outbox.store_event(UserCreated(user_id="2"))
        third = await outbox.store_event(UserCreated(user_id="3"))

        pending = await outbox.get_pending(limit=2)
        assert [e.entry_id for e in pending] == [first.entry_id, second.entry_id]

        remaining = await outbox.get_pending()
        assert [e.entry_id for e in remaining] == [third.entry_id]

    @pytest.mark.asyncio
    async def test_get_pending_excludes_non_pending(self, outbox) -> None:
        entry = await outbox.store_event(UserCreated(user_id="1"))
        # Entry is still in the pending queue when marked published —
        # get_pending must skip it and requeue the id, not drop it.
        await outbox.mark_published(entry.entry_id)
        assert await outbox.get_pending() == []

    @pytest.mark.asyncio
    async def test_mark_published_sets_status_and_timestamp(self, outbox) -> None:
        entry = await outbox.store_event(UserCreated(user_id="1"))
        await outbox.mark_published(entry.entry_id)
        assert entry.status is OutboxStatus.PUBLISHED
        assert entry.published_at is not None

    @pytest.mark.asyncio
    async def test_mark_failed_sets_error(self, outbox) -> None:
        entry = await outbox.store_event(UserCreated(user_id="1"))
        await outbox.mark_failed(entry.entry_id, "boom")
        assert entry.status is OutboxStatus.FAILED
        assert entry.error == "boom"

    @pytest.mark.asyncio
    async def test_mark_unknown_id_is_noop(self, outbox) -> None:
        await outbox.mark_published("missing")
        await outbox.mark_failed("missing", "boom")
        assert outbox.get_stats() == {"pending": 0, "published": 0, "failed": 0}

    @pytest.mark.asyncio
    async def test_retry_failed_returns_to_pending(self, outbox) -> None:
        entry = await outbox.store_event(UserCreated(user_id="1"))
        # Normal flow: the entry was dequeued (as the relay does) before it
        # failed, so retry re-queues it.
        await outbox.get_pending()
        await outbox.mark_failed(entry.entry_id, "boom")
        retried = await outbox.retry_failed()
        assert [e.entry_id for e in retried] == [entry.entry_id]
        assert entry.status is OutboxStatus.PENDING
        assert entry.error is None
        pending = await outbox.get_pending()
        assert [e.entry_id for e in pending] == [entry.entry_id]

    @pytest.mark.asyncio
    async def test_retry_failed_does_not_double_enqueue(self, outbox) -> None:
        # Failure path where the id is still queued (never dequeued): retry
        # must not enqueue it a second time.
        entry = await outbox.store_event(UserCreated(user_id="1"))
        await outbox.mark_failed(entry.entry_id, "boom")
        await outbox.retry_failed()
        pending = await outbox.get_pending()
        assert [e.entry_id for e in pending] == [entry.entry_id]

    @pytest.mark.asyncio
    async def test_get_stats(self, outbox) -> None:
        a = await outbox.store_event(UserCreated(user_id="1"))
        b = await outbox.store_event(UserCreated(user_id="2"))
        await outbox.mark_published(a.entry_id)
        await outbox.mark_failed(b.entry_id, "x")
        assert outbox.get_stats() == {"pending": 0, "published": 1, "failed": 1}

    @pytest.mark.asyncio
    async def test_clear_published_without_cutoff(self, outbox) -> None:
        a = await outbox.store_event(UserCreated(user_id="1"))
        b = await outbox.store_event(UserCreated(user_id="2"))
        await outbox.mark_published(a.entry_id)
        removed = await outbox.clear_published()
        assert removed == 1
        assert outbox.get_stats()["pending"] == 1

    @pytest.mark.asyncio
    async def test_clear_published_respects_cutoff(self, outbox) -> None:
        entry = await outbox.store_event(UserCreated(user_id="1"))
        await outbox.mark_published(entry.entry_id)
        # Cutoff in the past: the entry is NOT older than it — kept.
        removed = await outbox.clear_published(
            older_than=datetime.now(UTC) - timedelta(hours=1)
        )
        assert removed == 0
        # Cutoff in the future: the entry IS older than it — removed.
        removed = await outbox.clear_published(
            older_than=datetime.now(UTC) + timedelta(hours=1)
        )
        assert removed == 1


class _RecordingBus(InMemoryEventBus):
    """Event bus that records published events and can fail on demand."""

    def __init__(self) -> None:
        super().__init__()
        self.published: list[Any] = []
        self.fail: bool = False

    async def publish(self, event: DomainEvent) -> None:  # type: ignore[override]
        if self.fail:
            raise RuntimeError("bus down")
        self.published.append(event)


class TestOutboxRelay:
    @pytest.mark.asyncio
    async def test_process_pending_publishes_to_bus(self) -> None:
        outbox = InMemoryOutbox()
        bus = _RecordingBus()
        relay = OutboxRelay(outbox, bus)
        await outbox.store_event(UserCreated(user_id="1"))
        await outbox.store_event(OrderShipped(order_id="o1"))

        published, failed = await relay.process_pending()
        assert (published, failed) == (2, 0)
        assert [type(e) for e in bus.published] == [UserCreated, OrderShipped]
        assert outbox.get_stats()["published"] == 2

    @pytest.mark.asyncio
    async def test_publish_failure_is_marked_and_reported(self) -> None:
        outbox = InMemoryOutbox()
        bus = _RecordingBus()
        errors: list[Exception] = []

        async def on_error(entry: OutboxEntry, exc: Exception) -> None:
            errors.append(exc)

        relay = OutboxRelay(outbox, bus, on_publish_error=on_error)
        entry = await outbox.store_event(UserCreated(user_id="1"))
        bus.fail = True

        published, failed = await relay.process_pending()
        assert (published, failed) == (0, 1)
        assert entry.status is OutboxStatus.FAILED
        assert entry.error == "bus down"
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_batch_size_limits_processing(self) -> None:
        outbox = InMemoryOutbox()
        bus = _RecordingBus()
        relay = OutboxRelay(outbox, bus, batch_size=1)
        await outbox.store_event(UserCreated(user_id="1"))
        await outbox.store_event(UserCreated(user_id="2"))

        published, _ = await relay.process_pending()
        assert published == 1
        assert outbox.get_stats()["pending"] == 1

    @pytest.mark.asyncio
    async def test_relay_loop_processes_then_stops(self) -> None:
        outbox = InMemoryOutbox()
        bus = _RecordingBus()
        relay = OutboxRelay(outbox, bus)
        await outbox.store_event(UserCreated(user_id="1"))

        task = asyncio.create_task(relay.run_relay_loop(poll_interval=0.01))
        for _ in range(100):
            if len(bus.published) == 1:
                break
            await asyncio.sleep(0.01)
        relay.stop_relay()
        await asyncio.wait_for(task, timeout=5)
        assert len(bus.published) == 1

    @pytest.mark.asyncio
    async def test_relay_loop_survives_processing_errors(self) -> None:
        outbox = InMemoryOutbox()
        bus = _RecordingBus()
        relay = OutboxRelay(outbox, bus)
        await outbox.store_event(UserCreated(user_id="1"))

        task = asyncio.create_task(relay.run_relay_loop(poll_interval=0.01))
        # Wait until the first event is published, then break the bus.
        for _ in range(100):
            if len(bus.published) == 1:
                break
            await asyncio.sleep(0.01)
        bus.fail = True
        await outbox.store_event(OrderShipped(order_id="o2"))
        await asyncio.sleep(0.1)
        relay.stop_relay()
        await asyncio.wait_for(task, timeout=5)
        # First event went out; the second was marked failed, not lost.
        assert len(bus.published) == 1
        assert outbox.get_stats()["failed"] == 1

    @pytest.mark.asyncio
    async def test_relay_loop_survives_unexpected_exceptions(self) -> None:
        outbox = InMemoryOutbox()
        bus = _RecordingBus()
        relay = OutboxRelay(outbox, bus)

        async def exploding_get_pending(limit: int = 100) -> list[OutboxEntry]:
            raise RuntimeError("outbox exploded")

        relay.outbox.get_pending = exploding_get_pending  # type: ignore[method-assign]
        task = asyncio.create_task(relay.run_relay_loop(poll_interval=0.01))
        await asyncio.sleep(0.2)
        # The loop must still be alive after the unexpected exception.
        assert task.cancelled() is False
        relay.stop_relay()
        await asyncio.wait_for(task, timeout=5)

    @pytest.mark.asyncio
    async def test_relay_loop_backs_off_after_consecutive_errors(self) -> None:
        outbox = InMemoryOutbox()
        bus = _RecordingBus()
        bus.fail = True
        relay = OutboxRelay(outbox, bus, batch_size=1)

        # Two failure-only batches reach max_consecutive_errors=2.
        relay_run = asyncio.create_task(
            relay.run_relay_loop(poll_interval=0.01, max_consecutive_errors=2)
        )
        for i in range(2):
            await outbox.store_event(UserCreated(user_id=f"u{i}"))
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.2)
        relay.stop_relay()
        await asyncio.wait_for(relay_run, timeout=5)
        assert outbox.get_stats()["failed"] == 2
