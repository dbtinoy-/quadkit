"""Test harness for aggregate testing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.events.tests.testing.fakes import FakeEventStore

if TYPE_CHECKING:
    from quadkit.events.messages.event import Event


def given_events(
    aggregate_class: type,
    *events: Event,
    stream_id: str | None = None,
) -> Any:
    """Reconstitute an aggregate from a sequence of historical events."""
    agg = aggregate_class.__new__(aggregate_class)
    if hasattr(agg, "__init__"):
        try:
            agg.__init__()  # type: ignore[call-arg]
        except TypeError:
            pass

    if hasattr(agg, "load_from_history"):
        agg.load_from_history(list(events))
    elif hasattr(agg, "apply_events"):
        agg.apply_events(list(events))

    return agg


async def when_command(bus: Any, command: Any) -> Any:
    """Dispatch a command via the given bus and return the result."""
    return await bus.dispatch(command)


async def then_events(store: Any, stream_id: str) -> list[Event]:
    """Read all events from a stream for assertion."""
    return await store.read(stream_id)


class AggregateTestHarness:
    """Given/When/Then harness for aggregate testing."""

    def __init__(self, aggregate_class: type) -> None:
        self._class = aggregate_class
        self._history: list[Event] = []
        self._aggregate: Any = None
        self._result: Any = None
        self._store = FakeEventStore()

    def given(self, *events: Event) -> AggregateTestHarness:
        """Set up historical events."""
        self._history.extend(events)
        return self

    async def when(self, command: Any) -> AggregateTestHarness:
        """Apply a command to the aggregate (calls handle() if it exists)."""
        self._aggregate = given_events(self._class, *self._history)
        if hasattr(self._aggregate, "handle"):
            self._result = await self._aggregate.handle(command)
        return self

    def then_event(self, event_type: type, **attrs: Any) -> AggregateTestHarness:
        """Assert that the aggregate raised an event of the given type."""
        pending = self._get_pending_events()
        matches = [
            e
            for e in pending
            if isinstance(e, event_type)
            and all(getattr(e, k, None) == v for k, v in attrs.items())
        ]
        assert matches, (
            f"Expected {event_type.__name__} event. "
            f"Got: {[type(e).__name__ for e in pending]}"
        )
        return self

    def then_no_event(self, event_type: type) -> AggregateTestHarness:
        """Assert that no event of the given type was raised."""
        pending = self._get_pending_events()
        found = [e for e in pending if isinstance(e, event_type)]
        assert not found, f"Unexpected {event_type.__name__} event was raised"
        return self

    def then_result(self, expected: Any) -> AggregateTestHarness:
        """Assert the command handler returned the expected value."""
        assert self._result == expected, f"Expected {expected!r}, got {self._result!r}"
        return self

    def _get_pending_events(self) -> list[Event]:
        if self._aggregate is None:
            return []
        if hasattr(self._aggregate, "get_pending_events"):
            return self._aggregate.get_pending_events()
        if hasattr(self._aggregate, "pull_events"):
            return self._aggregate.pull_events()
        return []
