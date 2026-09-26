"""Test fakes for quadkit-events."""

from __future__ import annotations

from typing import Any

from quadkit.events.stores.memory import InMemoryEventStore


class FakeEventStore(InMemoryEventStore):
    """Test-friendly EventStoreProtocol with assertion helpers.

    Example::

        store = FakeEventStore()
        await store.append("order-1", [OrderCreated(order_id="order-1")])
        store.assert_stream_contains("order-1", "OrderCreated")
        store.assert_event_count("order-1", 1)
    """

    def assert_stream_contains(
        self,
        stream_id: str,
        event_type: str,
        **attrs: Any,
    ) -> None:
        """Assert that the stream contains at least one event of the given type."""
        events = self._streams.get(stream_id, [])
        matches = [
            e
            for e in events
            if type(e).__name__ == event_type
            and all(getattr(e, k, None) == v for k, v in attrs.items())
        ]
        assert matches, (
            f"No {event_type!r} event found in stream {stream_id!r}. "
            f"Events: {[type(e).__name__ for e in events]}"
        )

    def assert_event_count(self, stream_id: str, expected: int) -> None:
        """Assert the total number of events in a stream."""
        actual = len(self._streams.get(stream_id, []))
        assert actual == expected, (
            f"Stream {stream_id!r}: expected {expected} events, got {actual}"
        )

    def assert_no_events(self, stream_id: str) -> None:
        """Assert that the stream has no events."""
        self.assert_event_count(stream_id, 0)

    def get_stream(self, stream_id: str) -> list[Any]:
        """Return all events for a stream (for inline assertions)."""
        return list(self._streams.get(stream_id, []))
