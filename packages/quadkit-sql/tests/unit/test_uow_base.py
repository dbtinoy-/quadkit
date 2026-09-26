"""Unit tests for AbstractUnitOfWork (unit_of_work/base.py)."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.domain.unit_of_work import AbstractUnitOfWork


class _EventBus:
    def __init__(self) -> None:
        self.published: list[Any] = []

    async def publish(self, event: Any) -> None:
        self.published.append(event)


class _OutboxStore:
    def __init__(self) -> None:
        self.appended: list[list[Any]] = []

    async def append_batch(self, events: list[Any]) -> None:
        self.appended.append(list(events))


class _TestUOW(AbstractUnitOfWork):
    """Concrete UoW recording every flush."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.flushes = 0
        self.flushed: dict[str, list[Any]] = {"new": [], "dirty": [], "deleted": []}

    async def _flush(self) -> None:
        self.flushes += 1
        self.flushed = {
            "new": list(self._new),
            "dirty": list(self._dirty),
            "deleted": list(self._deleted),
        }


class TestEntityTracking:
    @pytest.mark.asyncio
    async def test_commit_flushes_all_tracked_entities(self) -> None:
        uow = _TestUOW()
        uow.register_new("e1")
        uow.register_dirty("e2")
        uow.register_deleted("e3")
        await uow.commit()
        assert uow.flushes == 1
        assert uow.flushed == {"new": ["e1"], "dirty": ["e2"], "deleted": ["e3"]}
        # State is cleared after commit.
        assert uow._new == [] and uow._dirty == [] and uow._deleted == []
        assert uow._committed is True

    @pytest.mark.asyncio
    async def test_rollback_discards_without_flushing(self) -> None:
        uow = _TestUOW()
        uow.register_new("e1")
        await uow.rollback()
        assert uow.flushes == 0
        assert uow._new == [] and uow._committed is False


class TestEventCollection:
    def test_collect_events_includes_registered_and_pulled(self) -> None:
        uow = _TestUOW()

        class Aggregate:
            def pull_events(self) -> list[Any]:
                return ["pulled"]

        agg = Aggregate()
        uow.register_event("direct")
        uow.register_new(agg)
        uow.register_dirty(agg)
        events = uow.collect_events()
        # direct + one pulled event per tracked reference (new and dirty).
        assert events == ["direct", "pulled", "pulled"]
        # collect_events does not clear; commit/rollback do.
        assert len(uow._events) == 1

    @pytest.mark.asyncio
    async def test_commit_publishes_via_event_bus_without_outbox(self) -> None:
        bus = _EventBus()
        uow = _TestUOW(event_bus=bus)
        uow.register_event("e")
        await uow.commit()
        assert bus.published == ["e"]

    @pytest.mark.asyncio
    async def test_commit_writes_outbox_instead_of_publishing(self) -> None:
        bus = _EventBus()
        outbox = _OutboxStore()
        uow = _TestUOW(event_bus=bus, outbox_store=outbox)
        uow.register_event("e")
        await uow.commit()
        assert outbox.appended == [["e"]]
        assert bus.published == []

    @pytest.mark.asyncio
    async def test_commit_without_events_publishes_nothing(self) -> None:
        bus = _EventBus()
        outbox = _OutboxStore()
        uow = _TestUOW(event_bus=bus, outbox_store=outbox)
        await uow.commit()
        assert bus.published == [] and outbox.appended == []

    @pytest.mark.asyncio
    async def test_commit_without_bus_or_outbox_succeeds(self) -> None:
        uow = _TestUOW()
        uow.register_event("e")
        await uow.commit()  # must not raise


class TestContextManager:
    @pytest.mark.asyncio
    async def test_commits_on_success(self) -> None:
        uow = _TestUOW()
        async with uow:
            uow.register_new("e")
        assert uow.flushes == 1

    @pytest.mark.asyncio
    async def test_rolls_back_and_reraises_on_error(self) -> None:
        uow = _TestUOW()
        with pytest.raises(RuntimeError, match="boom"):
            async with uow:
                uow.register_new("e")
                raise RuntimeError("boom")
        assert uow.flushes == 0
        assert uow._new == []

    @pytest.mark.asyncio
    async def test_enter_resets_committed_flag(self) -> None:
        uow = _TestUOW()
        await uow.commit()
        assert uow._committed is True
        async with uow:
            pass
        assert uow._committed is True
