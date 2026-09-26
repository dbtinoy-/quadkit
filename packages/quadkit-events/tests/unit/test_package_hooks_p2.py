"""P2 hook surface import verification for quadkit-events."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_events_hooks_root_module_exists() -> None:
    import quadkit.events
    from quadkit.events.hooks import (
        EventHandledHook,
        EventPublishedHook,
        EventStoredHook,
    )

    assert EventPublishedHook.__name__ == "EventPublishedHook"
    assert EventHandledHook.__name__ == "EventHandledHook"
    assert EventStoredHook.__name__ == "EventStoredHook"
    assert quadkit.events.EventPublishedHook is EventPublishedHook
    assert quadkit.events.EventHandledHook is EventHandledHook
    assert quadkit.events.EventStoredHook is EventStoredHook


def test_events_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.events.hooks import EventPublishedHook, EventStoredHook

    published = EventPublishedHook(event_type="UserCreated", aggregate_id="a1")
    stored = EventStoredHook(event_type="UserCreated", stream_id="users-1")

    assert is_dataclass(published)
    assert is_dataclass(stored)

    with pytest.raises(TypeError):
        EventStoredHook("UserCreated", "users-1")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        stored.stream_id = "other"  # type: ignore[misc]


def test_events_published_hook_aggregate_id_optional() -> None:
    from quadkit.events.hooks import EventPublishedHook

    hook = EventPublishedHook(event_type="UserCreated")
    assert hook.aggregate_id is None
