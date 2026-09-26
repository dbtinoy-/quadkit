"""Tests for @known_events decorator."""

from __future__ import annotations

import pytest
from quadkit.contracts.events.version_skew import EventTypeVersion
from quadkit.events.version_skew import KnownEventSetRegistry
from quadkit.events.version_skew.decorator import known_events


class TestKnownEventsDecorator:
    def test_registers_known_types_on_class(self) -> None:
        @known_events(consumer_id="test_consumer")
        class MyConsumer:
            KNOWN: list[EventTypeVersion] = [
                EventTypeVersion("foo.Bar", 1),
            ]

        assert hasattr(MyConsumer, "__known_event_registry__")
        reg: KnownEventSetRegistry = MyConsumer.__known_event_registry__
        assert reg.consumer_id == "test_consumer"
        assert reg.is_known("foo.Bar", 1)

    def test_decorator_raises_if_no_known_attribute(self) -> None:
        with pytest.raises(TypeError):

            @known_events(consumer_id="bad")
            class NoKnown:
                pass

    def test_multiple_consumers_have_separate_registries(self) -> None:
        @known_events(consumer_id="alice")
        class Alice:
            KNOWN = [EventTypeVersion("foo.Bar", 1)]

        @known_events(consumer_id="bob")
        class Bob:
            KNOWN = [EventTypeVersion("foo.Baz", 2)]

        alice_reg: KnownEventSetRegistry = Alice.__known_event_registry__
        bob_reg: KnownEventSetRegistry = Bob.__known_event_registry__
        assert alice_reg.is_known("foo.Bar", 1)
        assert not bob_reg.is_known("foo.Bar", 1)
        assert bob_reg.is_known("foo.Baz", 2)
