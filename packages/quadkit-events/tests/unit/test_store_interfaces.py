import inspect
import pytest
from quadkit.events.stores import HAS_POSTGRES, HAS_SQLITE

if not HAS_POSTGRES or not HAS_SQLITE:
    pytest.skip("SQL dependencies not installed", allow_module_level=True)

from quadkit.events.stores import (
    InMemoryEventStore,
    PostgresEventStore,
    SqliteEventStore,
)


def test_postgres_has_stored_events_since_method():
    assert hasattr(PostgresEventStore, "get_stored_events_since")
    assert inspect.iscoroutinefunction(PostgresEventStore.get_stored_events_since)


def test_postgres_has_timestamp_find_events_since():
    assert hasattr(PostgresEventStore, "find_events_since")
    # Implementation should be awaitable when bound to an instance; check it's callable
    assert callable(PostgresEventStore.find_events_since)


def test_sqlite_inherits_timestamp_find_events_since():
    # Sqlite relies on base implementation for timestamp-based streaming
    assert hasattr(SqliteEventStore, "find_events_since")
    # Base provides an async implementation (callable at class level)
    assert callable(SqliteEventStore.find_events_since)


def test_inmemory_event_store_has_stored_api():
    # InMemoryEventStore should implement basic methods at runtime
    store = InMemoryEventStore()
    assert hasattr(store, "append")
    assert hasattr(store, "read")
    assert hasattr(store, "find_events_since")
