"""Fail-closed checks around aggregate replay reads."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from quadkit.events.exceptions import EventStoreError

if TYPE_CHECKING:
    from quadkit.contracts.events import EventStoreProtocol


async def validated_stream_version(store: EventStoreProtocol, stream_id: str) -> int:
    """Require the optional async logical-version capability and a valid result."""
    get_version = getattr(store, "get_stream_version", None)
    if not callable(get_version):
        raise EventStoreError("Event store does not expose a stream version")
    value = get_version(stream_id)
    if not inspect.isawaitable(value):
        raise EventStoreError("Event store stream version is not awaitable")
    version = await value
    if type(version) is not int or version < 0:
        raise EventStoreError("Event store returned an invalid stream version")
    return version


async def read_consistent_history(
    store: EventStoreProtocol, stream_id: str, starting_version: int
) -> list[Any]:
    """Read a suffix with stable logical bounds and an expected event count.

    A custom store still owns the correctness and ordering of its results. Two
    version reads cannot establish transactional isolation or detect ABA resets.
    """
    before = await validated_stream_version(store, stream_id)
    if starting_version > before:
        raise EventStoreError("Snapshot version is ahead of the event stream version")
    events = await store.read(stream_id, from_version=starting_version + 1)
    after = await validated_stream_version(store, stream_id)
    if after != before:
        raise EventStoreError("Event stream version changed during history read")
    if not isinstance(events, list) or len(events) != before - starting_version:
        raise EventStoreError("Event stream history is incomplete")
    return events
