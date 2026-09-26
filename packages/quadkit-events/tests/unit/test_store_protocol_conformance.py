from quadkit.contracts.events import EventReplayProtocol
from quadkit.events import InMemoryEventStore


def test_inmemory_event_store_has_protocol_methods():
    store = InMemoryEventStore()
    # Basic runtime conformance checks
    assert hasattr(store, "append")
    assert hasattr(store, "read")
    assert hasattr(store, "get_stream_version")
    assert hasattr(store, "stream_all")
    assert callable(store.append)
    assert callable(store.read)
    assert callable(store.get_stream_version)
    assert isinstance(store, EventReplayProtocol)
