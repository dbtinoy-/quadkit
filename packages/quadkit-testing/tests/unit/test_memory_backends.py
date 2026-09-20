"""Tests for the in-memory backends: cache, audit logger, blob store, UoW."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from quadkit.contracts.audit import (
    AuditEntry,
    AuditEventSeverity,
    AuditQuery,
)
from quadkit.contracts.core.health import HealthStatus
from quadkit.contracts.domain.events import DomainEvent
from quadkit.testing.memory.audit import InMemoryAuditLogger
from quadkit.testing.memory.blob_store import InMemoryBlobStore
from quadkit.testing.memory.cache import InMemoryCacheBackend
from quadkit.testing.memory.event_bus import InMemoryEventBus
from quadkit.testing.memory.uow import InMemoryUnitOfWork

# ---------------------------------------------------------------------------
# InMemoryCacheBackend
# ---------------------------------------------------------------------------


class TestInMemoryCacheBackend:
    @pytest.mark.asyncio
    async def test_set_get_delete(self) -> None:
        cache = InMemoryCacheBackend()
        assert await cache.set("k", "v") is True
        assert await cache.get("k") == "v"
        assert await cache.delete("k") is True
        assert await cache.get("k") is None
        assert await cache.delete("k") is False

    @pytest.mark.asyncio
    async def test_missing_key_returns_none(self) -> None:
        cache = InMemoryCacheBackend()
        assert await cache.get("nope") is None

    @pytest.mark.asyncio
    async def test_ttl_expires_entries(self) -> None:
        cache = InMemoryCacheBackend()
        await cache.set("short", "v", ttl=0.02)
        assert await cache.get("short") == "v"
        await asyncio.sleep(0.04)
        assert await cache.get("short") is None
        assert await cache.exists("short") is False

    @pytest.mark.asyncio
    async def test_no_ttl_entries_never_expire(self) -> None:
        cache = InMemoryCacheBackend()
        await cache.set("k", "v")
        assert await cache.get("k") == "v"

    @pytest.mark.asyncio
    async def test_delete_many(self) -> None:
        cache = InMemoryCacheBackend()
        await cache.set("a", 1)
        await cache.set("b", 2)
        assert await cache.delete_many(["a", "missing"]) is True
        assert await cache.get("a") is None
        assert await cache.get("b") == 2

    @pytest.mark.asyncio
    async def test_get_many_and_set_many(self) -> None:
        cache = InMemoryCacheBackend()
        assert await cache.set_many({"a": 1, "b": 2}) is True
        assert await cache.get_many(["a", "b", "c"]) == {"a": 1, "b": 2}
        assert await cache.get_many([]) == {}

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        cache = InMemoryCacheBackend()
        await cache.set("a", 1)
        assert await cache.clear() is True
        assert await cache.get("a") is None

    @pytest.mark.asyncio
    async def test_health_check_reports_entry_count(self) -> None:
        cache = InMemoryCacheBackend()
        await cache.set("a", 1)
        await cache.set("b", 2)
        result = await cache.health_check()
        assert result.status is HealthStatus.HEALTHY
        assert result.component == "in_memory_cache"
        assert result.details == {"entries": 2}


# ---------------------------------------------------------------------------
# InMemoryAuditLogger
# ---------------------------------------------------------------------------


def _entry(
    action: str = "user.login",
    actor: str = "u1",
    **kwargs: Any,
) -> AuditEntry:
    return AuditEntry(action=action, actor_id=actor, **kwargs)


class TestInMemoryAuditLogger:
    @pytest.mark.asyncio
    async def test_log_and_count_and_all(self) -> None:
        audit = InMemoryAuditLogger()
        assert await audit.count() == 0
        first = _entry(action="a.first", actor="u1")
        second = _entry(action="a.second", actor="u2")
        await audit.log(first)
        await audit.log(second)
        assert await audit.count() == 2
        assert await audit.all() == [first, second]

    @pytest.mark.asyncio
    async def test_bounded_buffer_drops_oldest(self) -> None:
        audit = InMemoryAuditLogger(max_entries=3)
        for i in range(5):
            await audit.log(_entry(action=f"a.{i}"))
        assert await audit.count() == 3
        # Oldest two were dropped.
        assert [e.action for e in await audit.all()] == ["a.2", "a.3", "a.4"]

    @pytest.mark.asyncio
    async def test_query_filters_and_newest_first(self) -> None:
        audit = InMemoryAuditLogger()
        now = datetime.now(UTC)
        entries = [
            AuditEntry(
                action="user.login",
                actor_id="u1",
                resource_type="User",
                resource_id="u1",
                source="web",
                outcome="success",
                occurred_at=now - timedelta(seconds=30),
            ),
            AuditEntry(
                action="user.login",
                actor_id="u2",
                resource_type="User",
                resource_id="u2",
                source="api",
                outcome="failure",
                occurred_at=now - timedelta(seconds=20),
            ),
            AuditEntry(
                action="user.logout",
                actor_id="u1",
                resource_type="User",
                resource_id="u1",
                source="web",
                outcome="success",
                occurred_at=now - timedelta(seconds=10),
            ),
        ]
        for entry in entries:
            await audit.log(entry)

        assert len(await audit.query(AuditQuery(actor_id="u1"))) == 2
        # Newest-first ordering.
        actions = [e.action for e in await audit.query(AuditQuery(actor_id="u1"))]
        assert actions == ["user.logout", "user.login"]

        failures = await audit.query(AuditQuery(outcome="failure"))
        assert [e.actor_id for e in failures] == ["u2"]
        assert len(await audit.query(AuditQuery(resource_type="User"))) == 3
        assert len(await audit.query(AuditQuery(resource_id="u2"))) == 1
        assert len(await audit.query(AuditQuery(source="api"))) == 1
        # Only the now-10s entry is at/after now-15s.
        assert (
            len(await audit.query(AuditQuery(since=now - timedelta(seconds=15)))) == 1
        )
        # Only the now-30s entry is at/before now-25s.
        assert (
            len(await audit.query(AuditQuery(until=now - timedelta(seconds=25)))) == 1
        )
        assert len(await audit.query(AuditQuery(actor_id="nobody"))) == 0
        # Filters that discriminate within otherwise-matching entries.
        logins = await audit.query(AuditQuery(action="user.login"))
        assert [e.actor_id for e in logins] == ["u2", "u1"]  # newest first
        logouts = await audit.query(AuditQuery(action="user.logout"))
        assert [e.actor_id for e in logouts] == ["u1"]
        # Severity + a non-matching resource type (exclusion, not just match).
        await audit.log(
            AuditEntry(
                action="user.login",
                actor_id="u3",
                resource_type="User",
                resource_id="u3",
                source="web",
                outcome="success",
                severity=AuditEventSeverity.HIGH,
                occurred_at=now - timedelta(seconds=5),
            )
        )
        critical = await audit.query(AuditQuery(severity=AuditEventSeverity.HIGH))
        assert [e.actor_id for e in critical] == ["u3"]
        assert await audit.query(AuditQuery(resource_type="Session")) == []

    @pytest.mark.asyncio
    async def test_query_pagination(self) -> None:
        audit = InMemoryAuditLogger()
        for i in range(5):
            await audit.log(_entry(action=f"a.{i}", actor=f"u{i}"))
        page1 = await audit.query(AuditQuery(limit=2))
        page2 = await audit.query(AuditQuery(limit=2, offset=2))
        # Newest-first: u4, u3 | u2, u1
        assert [e.actor_id for e in page1] == ["u4", "u3"]
        assert [e.actor_id for e in page2] == ["u2", "u1"]

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        audit = InMemoryAuditLogger()
        await audit.log(_entry())
        await audit.clear()
        assert await audit.count() == 0
        assert await audit.all() == []


# ---------------------------------------------------------------------------
# InMemoryBlobStore
# ---------------------------------------------------------------------------


class TestInMemoryBlobStore:
    @pytest.mark.asyncio
    async def test_upload_bytes_and_download(self) -> None:
        store = InMemoryBlobStore()
        info = await store.upload("a.txt", b"hello", content_type="text/plain")
        assert info.path == "a.txt"
        assert info.size == 5
        assert info.content_type == "text/plain"
        assert isinstance(info.last_modified, datetime)
        assert await store.download("a.txt") == b"hello"

    @pytest.mark.asyncio
    async def test_upload_defaults_content_type(self) -> None:
        store = InMemoryBlobStore()
        info = await store.upload("x.bin", b"zz")
        assert info.content_type == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_upload_from_sync_file_object(self) -> None:
        store = InMemoryBlobStore()
        import io

        info = await store.upload(
            "note.txt", io.BytesIO(b"abc"), content_type="text/plain"
        )
        assert info.size == 3
        assert await store.download("note.txt") == b"abc"

    @pytest.mark.asyncio
    async def test_upload_from_async_iterator(self) -> None:
        store = InMemoryBlobStore()

        async def chunks():
            yield b"part1-"
            yield b"part2"

        info = await store.upload("big.bin", chunks())
        assert info.size == 11
        assert await store.download("big.bin") == b"part1-part2"

    @pytest.mark.asyncio
    async def test_download_missing_raises(self) -> None:
        store = InMemoryBlobStore()
        with pytest.raises(FileNotFoundError, match=r"missing\.bin"):
            await store.download("missing.bin")

    @pytest.mark.asyncio
    async def test_stream_chunks(self) -> None:
        store = InMemoryBlobStore()
        await store.upload("data.bin", b"0123456789")
        collected = [chunk async for chunk in store.stream("data.bin", chunk_size=4)]
        assert b"".join(collected) == b"0123456789"
        assert all(len(c) <= 4 for c in collected)

    @pytest.mark.asyncio
    async def test_exists_delete_info(self) -> None:
        store = InMemoryBlobStore()
        assert await store.exists("a") is False
        await store.upload("a", b"1")
        assert await store.exists("a") is True
        info = await store.info("a")
        assert info.size == 1
        with pytest.raises(FileNotFoundError):
            await store.info("missing")
        await store.delete("a")
        assert await store.exists("a") is False
        # Deleting a missing path is a no-op.
        await store.delete("a")

    @pytest.mark.asyncio
    async def test_get_presigned_url_and_clear(self) -> None:
        store = InMemoryBlobStore()
        await store.upload("r.pdf", b"%PDF")
        assert await store.get_presigned_url("r.pdf") == "/files/r.pdf?token=mock"
        store.clear()
        assert await store.exists("r.pdf") is False


# ---------------------------------------------------------------------------
# InMemoryUnitOfWork
# ---------------------------------------------------------------------------


class ThingChanged(DomainEvent):
    thing_id: str = ""


class _Aggregate:
    """Entity with a pull_events() method, as aggregate roots provide."""

    def __init__(self, event: DomainEvent) -> None:
        self._event = event

    def pull_events(self) -> list[DomainEvent]:
        return [self._event]


class TestInMemoryUnitOfWork:
    @pytest.mark.asyncio
    async def test_commit_publishes_registered_and_pulled_events(self) -> None:
        bus = InMemoryEventBus()
        seen: list[Any] = []

        async def handler(event: DomainEvent) -> None:
            seen.append(event)

        bus.subscribe(ThingChanged, handler)

        async with InMemoryUnitOfWork(event_bus=bus) as uow:
            uow.register_new(_Aggregate(ThingChanged(thing_id="pulled")))
            uow.register_event(ThingChanged(thing_id="registered"))

        # Registered events come first, then events pulled from aggregates.
        assert [e.thing_id for e in seen] == ["registered", "pulled"]

    @pytest.mark.asyncio
    async def test_commit_without_event_bus_is_safe(self) -> None:
        uow = InMemoryUnitOfWork()
        uow.register_event(ThingChanged(thing_id="x"))
        await uow.commit()  # must not raise with no bus configured

    @pytest.mark.asyncio
    async def test_rollback_discards_state(self) -> None:
        uow = InMemoryUnitOfWork()
        entity = _Aggregate(ThingChanged())
        uow.register_new(entity)
        uow.register_dirty(entity)
        uow.register_deleted(entity)
        await uow.rollback()
        assert uow.collect_events() == []

    @pytest.mark.asyncio
    async def test_context_manager_rolls_back_on_exception(self) -> None:
        rolled_back: list[bool] = []
        committed: list[bool] = []
        uow = InMemoryUnitOfWork()
        uow.on_rollback(lambda: rolled_back.append(True))
        uow.on_commit(lambda: committed.append(True))
        with pytest.raises(RuntimeError):
            async with uow:
                raise RuntimeError("fail")
        assert rolled_back == [True]
        assert committed == []

    @pytest.mark.asyncio
    async def test_context_manager_commits_on_success(self) -> None:
        committed: list[bool] = []
        uow = InMemoryUnitOfWork()
        uow.on_commit(lambda: committed.append(True))
        async with uow:
            pass
        assert committed == [True]
