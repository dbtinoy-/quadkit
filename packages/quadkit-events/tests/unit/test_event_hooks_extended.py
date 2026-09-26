"""Additional tests for event system hook emissions."""

from __future__ import annotations

import pytest

from quadkit.events.hooks import EventHandledHook, EventPublishedHook


class TestHookRegistryWithEventPayloads:
    """Tests for hook system with event-specific payloads."""

    def test_event_hooks_importable_from_quadkit_events(self) -> None:
        from quadkit.events.hooks import EventHandledHook, EventPublishedHook

        assert EventPublishedHook.__name__ == "EventPublishedHook"
        assert EventHandledHook.__name__ == "EventHandledHook"

    def test_event_hooks_are_frozen_dataclasses(self) -> None:
        from dataclasses import FrozenInstanceError, is_dataclass

        from quadkit.events.hooks import EventHandledHook, EventPublishedHook

        assert is_dataclass(EventPublishedHook)
        assert is_dataclass(EventHandledHook)

        published = EventPublishedHook(event_type="test")
        with pytest.raises(FrozenInstanceError):
            published.event_type = "modified"  # type: ignore[misc]

    def test_event_published_hook_accepts_aggregate_id(self) -> None:
        hook = EventPublishedHook(event_type="order.created", aggregate_id="agg-123")
        assert hook.event_type == "order.created"
        assert hook.aggregate_id == "agg-123"

    def test_event_published_hook_defaults_to_none_aggregate_id(self) -> None:
        hook = EventPublishedHook(event_type="test.event")
        assert hook.aggregate_id is None

    def test_event_handled_hook_requires_event_type_and_handler(self) -> None:
        hook = EventHandledHook(event_type="user.created", handler="UserCreatedHandler")
        assert hook.event_type == "user.created"
        assert hook.handler == "UserCreatedHandler"

    def test_event_stored_hook_importable(self) -> None:
        from quadkit.events.hooks import EventStoredHook

        hook = EventStoredHook(event_type="order.created", stream_id="stream-123")
        assert hook.event_type == "order.created"
        assert hook.stream_id == "stream-123"


class TestEventHookPriorityEnum:
    """Tests for hook priority in event contexts."""

    def test_hook_priority_importable(self) -> None:
        from quadkit.contracts.core.hooks import HookPriority

        assert HookPriority.EARLY == 50
        assert HookPriority.NORMAL == 100
        assert HookPriority.LATE == 200
