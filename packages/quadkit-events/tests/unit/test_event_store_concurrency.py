"""Concurrency-correctness tests for the event store append paths.

Covers three fixes:

- ``PostgresEventStore`` acquires a per-stream advisory lock inside the
  append transaction. Without it, the version check in ``_write_events``
  is check-then-insert: two READ COMMITTED transactions can both observe
  the same version, both pass the optimistic check, and both insert.
- ``SqliteEventStore`` maps a ``UNIQUE(stream_id, stream_version)``
  backstop violation to ``ConcurrencyError`` (consistent with the other
  stores' conflict semantics).
- ``MongoDBEventStore`` duplicate-key mapping reports
  ``expected_version=0`` correctly for fresh streams (``0`` is a
  legitimate version and must not be treated as "unset").
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest


def make_domain_event() -> Any:
    from quadkit.contracts.domain import DomainEvent

    return DomainEvent(
        aggregate_id=uuid4(),
        aggregate_type="TestAggregate",
        version=0,
    )


class _FakeTxn:
    def __init__(self, provider: "_FakeSqlProvider") -> None:
        self._provider = provider

    async def __aenter__(self) -> "_FakeTxn":
        self._provider.in_transaction += 1
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._provider.in_transaction -= 1


class _FakeSqlProvider:
    """Records SQL calls; serves a fixed stream version."""

    def __init__(self, version: int = 0, insert_error: Exception | None = None) -> None:
        self.version = version
        self.insert_error = insert_error
        self.calls: list[tuple[str, str]] = []
        self.in_transaction = 0

    def transaction(self, isolation_level: Any = None) -> _FakeTxn:
        return _FakeTxn(self)

    async def execute(self, sql: str, params: Any = None) -> Any:
        self.calls.append(("execute", sql))
        if "INSERT" in sql.upper() and self.insert_error is not None:
            raise self.insert_error
        return SimpleNamespace(rows=[])

    async def execute_query(self, sql: str, params: Any = None) -> Any:
        self.calls.append(("query", sql))
        return SimpleNamespace(rows=[{"version": self.version}])


class TestPostgresAdvisoryLock:
    def _store(self, provider: _FakeSqlProvider) -> Any:
        from quadkit.events.stores import (
            PostgresEventStore,
            PostgresEventStoreConfig,
        )

        config = PostgresEventStoreConfig(dsn="postgresql://test", events_table="events")
        return PostgresEventStore(config=config, provider=provider)

    @pytest.mark.asyncio
    async def test_append_takes_per_stream_lock_before_version_check(self) -> None:
        provider = _FakeSqlProvider(version=0)
        store = self._store(provider)

        await store.append("stream-1", [make_domain_event()], expected_version=0)

        kinds_sql = [sql for _kind, sql in provider.calls]
        assert provider.in_transaction == 0  # transaction closed
        # First statement inside the append must be the per-stream lock.
        lock_calls = [s for s in kinds_sql if "pg_advisory_xact_lock" in s]
        assert len(lock_calls) == 1
        assert "hashtextextended($1::text, 0)" in lock_calls[0]
        # The lock precedes both the version check and the insert.
        assert provider.calls[0][0] == "execute"
        assert "pg_advisory_xact_lock" in provider.calls[0][1]
        version_check_idx = next(
            i for i, (k, s) in enumerate(provider.calls) if "MAX(stream_version)" in s
        )
        insert_idx = next(
            i for i, (k, s) in enumerate(provider.calls) if "INSERT" in s.upper()
        )
        assert provider.calls.index(("execute", lock_calls[0])) < version_check_idx
        assert version_check_idx < insert_idx

    @pytest.mark.asyncio
    async def test_lock_key_carries_stream_id(self) -> None:
        provider = _FakeSqlProvider(version=0)
        store = self._store(provider)

        await store.append("my-stream", [make_domain_event()], expected_version=0)

        # The advisory lock is keyed by the stream id so different streams
        # never serialize against each other.
        lock_call = next(
            (k, s) for k, s in provider.calls if "pg_advisory_xact_lock" in s
        )
        _kind, sql = lock_call
        assert "$1" in sql


class TestSqliteUniqueViolationMapping:
    def _store(self, provider: _FakeSqlProvider) -> Any:
        from quadkit.events.stores.sqlite import SqliteEventStore

        return SqliteEventStore(provider=provider)

    @pytest.mark.asyncio
    async def test_unique_violation_maps_to_concurrency_error(self) -> None:
        from quadkit.events.exceptions import ConcurrencyError

        provider = _FakeSqlProvider(
            version=0,
            insert_error=Exception(
                "UNIQUE constraint failed: events.stream_id, events.stream_version"
            ),
        )
        store = self._store(provider)

        with pytest.raises(ConcurrencyError) as exc_info:
            await store.append("stream-1", [make_domain_event()], expected_version=0)

        # Fresh-stream expected version is 0 and must be reported as 0.
        assert exc_info.value.details["expected_version"] == 0

    @pytest.mark.asyncio
    async def test_integrity_error_type_maps_to_concurrency_error(self) -> None:
        import sqlite3

        from quadkit.events.exceptions import ConcurrencyError

        provider = _FakeSqlProvider(
            version=3, insert_error=sqlite3.IntegrityError("UNIQUE constraint failed")
        )
        store = self._store(provider)

        with pytest.raises(ConcurrencyError) as exc_info:
            await store.append("stream-1", [make_domain_event()], expected_version=3)

        assert exc_info.value.details["expected_version"] == 3

    @pytest.mark.asyncio
    async def test_unrelated_errors_propagate(self) -> None:
        provider = _FakeSqlProvider(
            version=0, insert_error=RuntimeError("boom")
        )
        store = self._store(provider)

        with pytest.raises(RuntimeError, match="boom"):
            await store.append("stream-1", [make_domain_event()], expected_version=0)


class _FakeAsyncIter:
    def __init__(self, items: list[Any]) -> None:
        self._items = iter(items)

    def __aiter__(self) -> "_FakeAsyncIter":
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None


class _FakeCollection:
    def __init__(
        self,
        insert_error: Exception | None = None,
        delete_many_result: int = 0,
    ) -> None:
        self.insert_error = insert_error
        self.delete_many_result = delete_many_result
        self.deleted_filters: list[Any] = []

    async def find_one(self, query: Any) -> Any:
        return None

    async def find(self, query: Any, sort: Any = None, limit: int = 0) -> Any:
        return _FakeAsyncIter([])

    async def insert_many(self, docs: list[Any]) -> None:
        if self.insert_error is not None:
            raise self.insert_error

    async def find_one_and_update(
        self, query: Any, update: Any, upsert: bool = False, return_document: bool = True
    ) -> Any:
        # Counters collection only: always serve an incremented counter.
        return {"_id": "global_sequence", "value": 1}

    async def create_index(self, keys: Any, unique: bool = False) -> None:
        pass

    async def delete_many(self, query: Any) -> Any:
        self.deleted_filters.append(query)
        return SimpleNamespace(matched_count=self.delete_many_result)


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _FakeDocumentStore:
    def __init__(self, events_collection: _FakeCollection) -> None:
        self._events = events_collection
        self._connected = True

    def is_connected(self) -> bool:
        return True

    async def connect(self) -> None:
        pass

    def collection(self, name: str) -> _FakeCollection:
        if name == "counters":
            return _FakeCollection()
        return self._events

    def session(self) -> Any:
        return _FakeSession()


class TestMongoDuplicateKeyZeroVersion:
    @pytest.mark.asyncio
    async def test_duplicate_key_on_fresh_stream_reports_version_zero(self) -> None:
        from quadkit.events.exceptions import ConcurrencyError
        from quadkit.events.stores.mongodb import (
            MongoDBConfig,
            MongoDBEventStore,
        )

        events = _FakeCollection(
            insert_error=Exception(
                "mongo bulk write error: "
                "E11000 duplicate key error collection: db.events"
            )
        )
        config = MongoDBConfig(uri="mongodb://test")
        store = MongoDBEventStore(_FakeDocumentStore(events), config)
        await store.connect()

        with pytest.raises(ConcurrencyError) as exc_info:
            await store.append("fresh-stream", [make_domain_event()], expected_version=0)

        # expected_version=0 must survive as 0 (the pre-fix
        # ``expected_version or current_version`` coerced it to the
        # observed version, misreporting fresh-stream conflicts).
        assert exc_info.value.details["expected_version"] == 0

    @pytest.mark.asyncio
    async def test_compact_purges_up_to_version_inclusive(self) -> None:
        from quadkit.events.stores.mongodb import (
            MongoDBConfig,
            MongoDBEventStore,
        )

        events = _FakeCollection(delete_many_result=3)
        config = MongoDBConfig(uri="mongodb://test")
        store = MongoDBEventStore(_FakeDocumentStore(events), config)
        await store.connect()

        purged = await store.compact("stream-1", up_to_version=7)

        assert purged == 3
        assert events.deleted_filters == [
            {"stream_id": "stream-1", "stream_version": {"$lte": 7}}
        ]
