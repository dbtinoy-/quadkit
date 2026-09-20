"""Unit tests for quadkit.testing.fakes.

Tests the fakes that were added in the REVIEW-driven redesign:
FakeClock, FakeUnitOfWork, FakeConfig — as well as quick smoke-tests for the
pre-existing fakes to guard against regressions.
"""

from __future__ import annotations

import asyncio

import pytest

from quadkit.testing.fakes import (
    FakeCache,
    FakeClock,
    FakeCommandBus,
    FakeConfig,
    FakeEventBus,
    FakeLogger,
    FakeMetricsCollector,
    FakeQueryBus,
    FakeStateStore,
    FakeUnitOfWork,
)

# ---------------------------------------------------------------------------
# FakeClock
# ---------------------------------------------------------------------------


class TestFakeClock:
    """FakeClock behaves like a controllable clock."""

    def test_initial_state(self) -> None:
        clock = FakeClock()
        t = clock.now()
        assert t is not None

    def test_advance_moves_time_forward(self) -> None:
        clock = FakeClock()
        before = clock.monotonic()
        clock.advance(5.0)
        after = clock.monotonic()
        assert after - before == pytest.approx(5.0)

    def test_freeze_sets_clock_to_given_datetime(self) -> None:
        from datetime import UTC, datetime

        fixed = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        clock = FakeClock()
        clock.freeze(at=fixed)
        assert clock.now() == fixed
        # Monotonic offset should be reset to 0
        t1 = clock.monotonic()
        t2 = clock.monotonic()
        assert t1 == t2

    def test_tick_increments_by_default_step(self) -> None:
        clock = FakeClock()
        t1 = clock.monotonic()
        clock.tick()
        t2 = clock.monotonic()
        assert t2 > t1


# ---------------------------------------------------------------------------
# FakeUnitOfWork
# ---------------------------------------------------------------------------


class MockEntity:
    def __init__(self, id_: str) -> None:
        self.id = id_


class TestFakeUnitOfWork:
    """FakeUnitOfWork tracks entity changes and events."""

    @pytest.mark.asyncio
    async def test_register_and_commit(self) -> None:
        uow = FakeUnitOfWork()
        entity = MockEntity("e1")
        uow.register_new(entity)
        await uow.commit()
        assert uow.committed is True
        assert entity in uow.new

    @pytest.mark.asyncio
    async def test_rollback_clears_state(self) -> None:
        uow = FakeUnitOfWork()
        uow.register_new(MockEntity("e1"))
        uow.register_event({"type": "SomeEvent"})
        await uow.rollback()
        assert uow.rolled_back is True
        assert uow.new == []
        assert uow.events == []

    @pytest.mark.asyncio
    async def test_context_manager_commits_on_success(self) -> None:
        uow = FakeUnitOfWork()
        async with uow:
            uow.register_dirty(MockEntity("e2"))
        assert uow.committed is True

    @pytest.mark.asyncio
    async def test_context_manager_rolls_back_on_exception(self) -> None:
        uow = FakeUnitOfWork()

        async def _trigger() -> None:
            async with uow:
                uow.register_new(MockEntity("e3"))
                raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await _trigger()
        assert uow.rolled_back is True
        assert uow.new == []

    @pytest.mark.asyncio
    async def test_collect_events(self) -> None:
        uow = FakeUnitOfWork()
        uow.register_event({"type": "A"})
        uow.register_event({"type": "B"})
        events = uow.collect_events()
        assert len(events) == 2
        assert events[0]["type"] == "A"

    @pytest.mark.asyncio
    async def test_publishes_events_to_fake_event_bus_on_commit(self) -> None:
        bus = FakeEventBus()
        uow = FakeUnitOfWork(event_bus=bus)

        class MyEvent:
            pass

        evt = MyEvent()
        uow.register_event(evt)
        await uow.commit()
        bus.assert_published(MyEvent)


# ---------------------------------------------------------------------------
# FakeConfig
# ---------------------------------------------------------------------------


class TestFakeConfig:
    """FakeConfig satisfies the ConfigProtocol for tests."""

    def test_get_returns_value(self) -> None:
        cfg = FakeConfig({"key": "value"})
        assert cfg.get("key") == "value"

    def test_get_returns_default_when_missing(self) -> None:
        cfg = FakeConfig()
        assert cfg.get("missing") is None
        assert cfg.get("missing", "fallback") == "fallback"

    def test_dotted_key_traversal(self) -> None:
        cfg = FakeConfig({"database": {"url": "sqlite:///db"}})
        assert cfg.get("database.url") == "sqlite:///db"

    def test_get_section(self) -> None:
        cfg = FakeConfig({"cache": {"backend": "memory", "ttl": 60}})
        section = cfg.get_section("cache")
        assert section["backend"] == "memory"
        assert section["ttl"] == 60

    def test_set_and_get(self) -> None:
        cfg = FakeConfig()
        cfg.set("feature.enabled", True)
        assert cfg.get("feature.enabled") is True

    def test_set_nested_creates_intermediate_dicts(self) -> None:
        cfg = FakeConfig()
        cfg.set("a.b.c", 42)
        assert cfg.get("a.b.c") == 42


# ---------------------------------------------------------------------------
# Smoke tests — pre-existing fakes
# ---------------------------------------------------------------------------


class TestFakeCache:
    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        cache = FakeCache()
        await cache.set("k", "v")
        assert await cache.get("k") == "v"

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        cache = FakeCache()
        await cache.set("k", "v")
        deleted = await cache.delete("k")
        assert deleted is True
        assert await cache.get("k") is None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self) -> None:
        cache = FakeCache()
        await cache.set("k", "v", ttl=0.05)
        await asyncio.sleep(0.1)
        assert await cache.get("k") is None

    @pytest.mark.asyncio
    async def test_assert_helpers(self) -> None:
        cache = FakeCache()
        await cache.set("x", 1)
        cache.assert_has_key("x")
        cache.assert_value("x", 1)


class TestFakeEventBus:
    @pytest.mark.asyncio
    async def test_publish_and_assert(self) -> None:
        bus = FakeEventBus()

        class Evt:
            pass

        await bus.publish(Evt())
        bus.assert_published(Evt)
        bus.assert_published_once(Evt)

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        bus = FakeEventBus()

        class Evt:
            pass

        await bus.publish(Evt())
        bus.clear()
        bus.assert_not_published(Evt)


class TestFakeLogger:
    def test_log_and_assert(self) -> None:
        log = FakeLogger()
        log.info("something happened", key="value")
        log.assert_logged("info", "something happened")
        log.assert_not_logged("error", "something happened")

    def test_clear(self) -> None:
        log = FakeLogger()
        log.warning("w")
        log.clear()
        assert log.entries == []


class TestFakeMetricsCollector:
    def test_counter_incremented(self) -> None:
        m = FakeMetricsCollector()
        m.increment("requests")
        m.increment("requests")
        m.assert_counter("requests", 2.0)
        m.assert_counter_incremented("requests")

    def test_gauge(self) -> None:
        m = FakeMetricsCollector()
        m.gauge("queue_depth", 5.0)
        m.assert_gauge("queue_depth", 5.0)


class TestFakeStateStore:
    @pytest.mark.asyncio
    async def test_set_get_delete(self) -> None:
        store = FakeStateStore()
        await store.set("k", "v")
        assert await store.get("k") == "v"
        assert await store.exists("k") is True
        await store.delete("k")
        assert await store.get("k") is None


class TestFakeCommandBus:
    @pytest.mark.asyncio
    async def test_dispatch_records(self) -> None:
        bus = FakeCommandBus()

        class Cmd:
            pass

        cmd = Cmd()
        await bus.dispatch(cmd)
        bus.assert_dispatched(Cmd, count=1)

    def test_assert_not_dispatched(self) -> None:
        bus = FakeCommandBus()

        class Cmd:
            pass

        bus.assert_not_dispatched(Cmd)


class TestFakeQueryBus:
    @pytest.mark.asyncio
    async def test_when_returns_canned_result(self) -> None:
        bus = FakeQueryBus()

        class Query:
            pass

        bus.when(Query, "some_result")
        result = await bus.execute(Query())
        assert result == "some_result"
