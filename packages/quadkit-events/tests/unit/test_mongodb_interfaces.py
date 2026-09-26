import inspect
import pytest
from quadkit.events.stores import HAS_MONGODB

if not HAS_MONGODB:
    pytest.skip("MongoDB dependencies not installed", allow_module_level=True)

from quadkit.events.stores.mongodb import MongoDBEventStore


def test_mongodb_class_has_core_methods():
    # We don't connect; just verify the class exposes the expected methods
    assert hasattr(MongoDBEventStore, "_get_next_sequence")
    assert inspect.iscoroutinefunction(MongoDBEventStore._get_next_sequence)
    assert hasattr(MongoDBEventStore, "get_stream_version")
    assert callable(MongoDBEventStore.get_stream_version)
    assert hasattr(MongoDBEventStore, "stream_all")
    assert callable(MongoDBEventStore.stream_all)
    assert hasattr(MongoDBEventStore, "find_by_type")
    assert inspect.iscoroutinefunction(MongoDBEventStore.find_by_type)
    assert hasattr(MongoDBEventStore, "get_events_count")
    assert inspect.iscoroutinefunction(MongoDBEventStore.get_events_count)
    assert hasattr(MongoDBEventStore, "watch_events")
    assert callable(MongoDBEventStore.watch_events)
