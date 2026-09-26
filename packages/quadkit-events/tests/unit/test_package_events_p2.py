"""P2 guardrail: quadkit-events must expose a canonical root events module."""

from __future__ import annotations


def test_events_events_root_module_exists() -> None:
    from quadkit.events.events import EventPublishedEvent, ProjectionUpdatedEvent

    assert EventPublishedEvent.__name__ == "EventPublishedEvent"
    assert ProjectionUpdatedEvent.__name__ == "ProjectionUpdatedEvent"


def test_events_events_re_exported_from_package_root() -> None:
    import quadkit.events as events_pkg

    assert hasattr(events_pkg, "EventPublishedEvent")
    assert hasattr(events_pkg, "ProjectionUpdatedEvent")
