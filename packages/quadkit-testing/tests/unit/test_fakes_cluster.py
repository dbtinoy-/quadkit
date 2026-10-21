"""Tests for the fakes cluster (in-process test doubles).

Covers every module in :mod:`quadkit.testing.fakes`: redis, audit, buses,
cache, clock, config, events, governance, lifecycle, logging, monitoring,
secrets re-export, and tracing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# FakeRedisClient
# ---------------------------------------------------------------------------


async def test_redis_client_basic_set_get_delete() -> None:
    from quadkit.testing.fakes.redis import FakeRedisClient

    client = FakeRedisClient()
    assert await client.ping() is True

    assert await client.set("k", "v") is True
    assert await client.get("k") == "v"
    assert await client.get("missing") is None
    assert await client.exists("k", "missing") == 1
    assert await client.delete("k", "missing") == 1
    assert await client.get("k") is None
    await client.close()


async def test_redis_client_set_conditions_and_ttl() -> None:
    from quadkit.testing.fakes.redis import FakeRedisClient

    client = FakeRedisClient()
    assert await client.set("a", "1") is True
    assert await client.set("a", "2", nx=True) is None  # exists
    assert await client.get("a") == "1"
    assert await client.set("b", "x", xx=True) is None  # missing
    assert await client.set("b", "x", xx=True, nx=False) is None

    await client.set("c", "v", px=50)
    assert await client.ttl("c") >= 0
    time.sleep(0.06)
    assert await client.get("c") is None
    assert await client.ttl("c") == -2

    await client.set("d", "v")
    assert await client.ttl("d") == -1
    assert await client.expire("d", 100) is True
    assert await client.expire("ghost", 5) is False

    # keepttl preserves the previous expiry
    await client.set("e", "1", ex=50)
    await client.set("e", "2", keepttl=True)
    assert await client.ttl("e") >= 0
    assert await client.flushdb() is True
    assert await client.exists("d", "e") == 0


# ---------------------------------------------------------------------------
# FakeAuditLogger
# ---------------------------------------------------------------------------


def _entry(**overrides: Any) -> Any:
    from quadkit.contracts.audit import AuditEntry

    defaults: dict[str, Any] = {
        "action": "user.login",
        "actor_id": "u-1",
        "occurred_at": datetime(2024, 5, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return AuditEntry(**defaults)


async def test_audit_logger_query_filters_and_ordering() -> None:
    from quadkit.contracts.audit import AuditQuery
    from quadkit.testing.fakes.audit import FakeAuditLogger

    fake = FakeAuditLogger()
    await fake.log(_entry())
    await fake.log(_entry(actor_id="u-2", action="user.logout"))
    await fake.log(_entry(resource_type="order", resource_id="o-1", severity="warn"))

    assert len(fake.entries) == 3

    by_actor = await fake.query(AuditQuery(actor_id="u-2"))
    assert len(by_actor) == 1 and by_actor[0].actor_id == "u-2"

    by_action = await fake.query(AuditQuery(action="user.logout"))
    assert len(by_action) == 1

    by_resource = await fake.query(AuditQuery(resource_type="order", resource_id="o-1"))
    assert len(by_resource) == 1

    by_severity = await fake.query(AuditQuery(severity="warn"))
    assert len(by_severity) == 1

    # newest-first ordering + offset/limit
    all_entries = await fake.query(AuditQuery(limit=2))
    assert len(all_entries) == 2
    assert all_entries[0].resource_type == "order"  # last logged first
    assert all_entries[1].actor_id == "u-2"
    assert (await fake.query(AuditQuery(limit=2, offset=1)))[0].actor_id == "u-2"

    # since / until
    since = await fake.query(AuditQuery(since=datetime(2024, 5, 2, tzinfo=UTC)))
    assert since == []
    until = await fake.query(AuditQuery(until=datetime(2024, 4, 30, tzinfo=UTC)))
    assert until == []

    assert await fake.count(AuditQuery()) == 3


async def test_audit_logger_append_delete_expired() -> None:
    from quadkit.contracts.audit import AuditQuery
    from quadkit.testing.fakes.audit import FakeAuditLogger

    fake = FakeAuditLogger()
    await fake.append(_entry(metadata={"__expires_at": "2020-01-01T00:00:00+00:00"}))
    await fake.append(_entry(metadata={"__expires_at": "not-a-date"}))
    await fake.append(_entry())

    removed = await fake.delete_expired(cutoff=datetime(2024, 1, 1, tzinfo=UTC))
    assert removed == 1
    assert len(fake.entries) == 2
    assert await fake.count(AuditQuery()) == 2


# ---------------------------------------------------------------------------
# FakeCommandBus / FakeQueryBus
# ---------------------------------------------------------------------------


@dataclass
class CreateThing:
    name: str = "thing"


@dataclass
class GetThing:
    name: str = "thing"


async def test_fake_command_bus_dispatch_and_assertions() -> None:
    from quadkit.testing.fakes.buses import FakeCommandBus

    bus = FakeCommandBus()

    class _Handler:
        def __init__(self) -> None:
            self.handled: list[Any] = []

        async def handle(self, command: Any) -> str:
            self.handled.append(command)
            return "ok"

    handler = _Handler()
    bus.register(CreateThing, handler)

    result = await bus.dispatch(CreateThing("a"))
    assert result == "ok"
    await bus.dispatch(CreateThing("b"))
    await bus.dispatch(GetThing("c"))  # no handler -> None

    assert len(bus.dispatched) == 3
    assert len(bus.dispatched_of_type(CreateThing)) == 2
    bus.assert_dispatched(CreateThing, count=2)
    bus.assert_dispatched(GetThing)
    with pytest.raises(AssertionError, match="NOT be dispatched"):
        bus.assert_not_dispatched(CreateThing)
    with pytest.raises(AssertionError, match="but found 1"):
        bus.assert_dispatched(GetThing, count=2)

    bus.clear()
    assert bus.dispatched == []


async def test_fake_query_bus_canned_and_handlers() -> None:
    from quadkit.testing.fakes.buses import FakeQueryBus

    bus = FakeQueryBus()
    user = {"id": "u1"}
    bus.when(GetThing, return_value=user)
    assert await bus.execute(GetThing("x")) == user

    class _Handler:
        async def handle(self, query: Any) -> str:
            return "handled"

    bus.register(CreateThing, _Handler())
    assert await bus.execute(CreateThing("y")) == "handled"

    assert len(bus.executed) == 2
    assert len(bus.executed_of_type(GetThing)) == 1
    bus.clear()
    assert bus.executed == []


# ---------------------------------------------------------------------------
# FakeCache / FakeStateStore
# ---------------------------------------------------------------------------


async def test_fake_cache_set_get_ttl_and_assertions() -> None:
    from quadkit.testing.fakes.cache import FakeCache, FakeStateStore

    cache = FakeCache()
    await cache.set("k", "v", ttl=60)
    assert await cache.get("k") == "v"
    assert await cache.get("missing", "dflt") == "dflt"
    cache.assert_has_key("k")
    cache.assert_value("k", "v")
    assert cache.stored_keys == ["k"]
    with pytest.raises(AssertionError, match="not in cache"):
        cache.assert_has_key("nope")
    with pytest.raises(AssertionError, match="expected"):
        cache.assert_value("k", "other")

    await cache.set("short", "x", ttl=0.02)
    time.sleep(0.04)
    assert await cache.get("short") is None

    assert await cache.delete("k") is True
    assert await cache.delete("k") is False
    await cache.clear()
    assert cache.stored_keys == []

    store = FakeStateStore()
    await store.set("s:1", {"user": "u1"})
    assert await store.get("s:1") == {"user": "u1"}
    assert await store.exists("s:1") is True
    assert await store.delete("s:1") is True
    assert await store.get("s:1") is None


# ---------------------------------------------------------------------------
# Clocks
# ---------------------------------------------------------------------------


def test_system_clock_and_fake_clock() -> None:
    from quadkit.testing.fakes.clock import Clock, FakeClock, SystemClock

    system = SystemClock()
    assert isinstance(system, Clock)
    assert system.now().tzinfo == UTC
    assert system.monotonic() >= 0
    assert system.time() > 0

    fake = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    assert fake.now().year == 2026
    assert fake.time() == fake.now().timestamp()
    fake.advance(3600)
    assert fake.now().hour == 1
    assert fake.monotonic() == 3600.0
    fake.tick()
    assert fake.monotonic() == 3601.0
    fake.freeze(datetime(2025, 6, 15, 12, 0, tzinfo=UTC))
    assert fake.now().year == 2025
    assert fake.monotonic() == 0.0

    default = FakeClock()
    assert default.now().tzinfo == UTC


def test_fake_and_system_clocks_conform_to_clock_protocol() -> None:
    """Both clocks satisfy the contracts protocol the ambient seam is typed on.

    ``quadkit.contracts.core.clock.ClockProtocol`` requires four members —
    ``now``, ``monotonic``, ``timestamp`` and ``time``. ``timestamp()`` used to
    be missing here, so ``quadkit.primitives.clock.use(FakeClock(...))`` was
    accepted and then failed with ``AttributeError`` the first time anything read
    ``clock.timestamp()``.
    """
    from quadkit.contracts.core.clock import ClockProtocol
    from quadkit.testing.clock import FixedClock
    from quadkit.testing.fakes.clock import FakeClock, SystemClock

    clocks = (
        SystemClock(),
        FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
        FixedClock(),
    )
    for clock in clocks:
        assert isinstance(clock, ClockProtocol), type(clock).__name__
        for member in ("now", "monotonic", "timestamp", "time"):
            assert hasattr(clock, member), f"{type(clock).__name__}.{member}"


def test_fake_clock_can_back_the_ambient_clock_seam() -> None:
    """Installing a FakeClock through the ambient seam reaches every primitive."""
    from quadkit.primitives import clock as ambient
    from quadkit.testing.fakes.clock import FakeClock

    with ambient.use(FakeClock(datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC))):
        assert ambient.now() == datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
        assert ambient.timestamp() == ambient.now().timestamp()
        assert isinstance(ambient.monotonic(), float)


# ---------------------------------------------------------------------------
# FakeConfig
# ---------------------------------------------------------------------------


def test_fake_config_dotted_access_and_sections() -> None:
    from quadkit.contracts.core.config import Environment
    from quadkit.testing.fakes.config import FakeConfig

    config = FakeConfig({"database": {"url": "sqlite:///:memory:"}, "flat.key": 7})
    assert config.get("database.url") == "sqlite:///:memory:"
    assert config.get("flat.key") == 7  # literal flat key wins
    assert config.get("missing.path", "d") == "d"
    assert config.has_section("database") is True
    assert config.has_section("flat.key") is False

    config.set("cache.backend", "memory")
    assert config.get("cache.backend") == "memory"

    section = config.get_section("database")
    assert section == {"url": "sqlite:///:memory:"}

    class _Model:
        def __init__(self, **kwargs: Any) -> None:
            self.data = kwargs

    model = config.get_section("database", _Model)
    assert isinstance(model, _Model)

    assert config.environment == Environment.TEST
    assert config.is_debug is False
    assert config.is_testing is True
    assert config.is_production is False
    assert config.is_development is False
    assert config.is_staging is False


# ---------------------------------------------------------------------------
# FakeEventBus
# ---------------------------------------------------------------------------


@dataclass
class UserCreated:
    user_id: str = "u-1"


@dataclass
class UserDeleted:
    user_id: str = "u-1"


async def test_fake_event_bus_publish_priority_and_assertions() -> None:
    from quadkit.testing.fakes.events import FakeEventBus

    bus = FakeEventBus()
    order: list[str] = []

    async def late(e: Any) -> None:
        order.append("late")

    async def early(e: Any) -> None:
        order.append("early")

    class _Handler:
        async def handle(self, e: Any) -> None:
            order.append("handler")

    bus.subscribe(UserCreated, late)
    bus.subscribe(UserCreated, early, priority=-1)
    bus.subscribe(UserCreated, _Handler())

    await bus.publish(UserCreated("u-9"))
    assert order == ["early", "late", "handler"]

    assert len(bus.published) == 1
    assert len(bus.published_of_type(UserCreated)) == 1
    bus.assert_published(UserCreated, count=1, user_id="u-9")
    bus.assert_published_once(UserCreated, user_id="u-9")
    bus.assert_not_published(UserDeleted)
    with pytest.raises(AssertionError, match="but found:"):
        bus.assert_published(UserDeleted)
    with pytest.raises(AssertionError, match="No .* matched attributes"):
        bus.assert_published(UserCreated, user_id="other")
    with pytest.raises(AssertionError, match="NOT be published"):
        bus.assert_not_published(UserCreated)

    await bus.publish(UserDeleted("u-9"))
    bus.assert_events_in_order(UserCreated, UserDeleted)
    with pytest.raises(AssertionError):
        bus.assert_events_in_order(UserDeleted, UserCreated)

    bus.unsubscribe(UserCreated, late)
    order.clear()
    await bus.publish(UserCreated("u-2"))
    assert order == ["early", "handler"]  # late unsubscribed
