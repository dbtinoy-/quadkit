"""Per-consumer known-event-set registry."""

from __future__ import annotations

from quadkit.contracts.events.version_skew import EventTypeVersion


class KnownEventSetRegistry:
    """Tracks the set of (event_type, schema_version) pairs a consumer handles.

    Each consumer gets its own registry, keyed by ``consumer_id``.
    """

    def __init__(self, consumer_id: str) -> None:
        self._consumer_id = consumer_id
        self._known: set[EventTypeVersion] = set()

    @property
    def consumer_id(self) -> str:
        return self._consumer_id

    @property
    def all_known(self) -> frozenset[EventTypeVersion]:
        return frozenset(self._known)

    def register(self, types: list[EventTypeVersion]) -> None:
        self._known.update(types)

    def is_known(self, event_type: str, version: int) -> bool:
        return EventTypeVersion(event_type, version) in self._known

    def has_type(self, event_type: str) -> bool:
        return any(t.event_type == event_type for t in self._known)


__all__ = ["KnownEventSetRegistry"]
