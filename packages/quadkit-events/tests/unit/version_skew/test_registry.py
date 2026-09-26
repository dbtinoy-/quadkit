"""Tests for KnownEventSetRegistry."""

from __future__ import annotations

import pytest
from quadkit.contracts.events.version_skew import EventTypeVersion
from quadkit.events.version_skew.registry import KnownEventSetRegistry


class TestKnownEventSetRegistry:
    def test_initial_state_is_empty(self) -> None:
        reg = KnownEventSetRegistry(consumer_id="my_consumer")
        assert reg.consumer_id == "my_consumer"
        assert not reg.all_known

    def test_register_single_type(self) -> None:
        reg = KnownEventSetRegistry("my_consumer")
        reg.register([EventTypeVersion("foo.Bar", 1)])
        assert reg.is_known("foo.Bar", 1)
        assert not reg.is_known("foo.Bar", 2)
        assert not reg.is_known("foo.Baz", 1)

    def test_register_multiple_versions(self) -> None:
        reg = KnownEventSetRegistry("my_consumer")
        reg.register([
            EventTypeVersion("foo.Bar", 1),
            EventTypeVersion("foo.Bar", 2),
            EventTypeVersion("foo.Baz", 1),
        ])
        assert reg.is_known("foo.Bar", 1)
        assert reg.is_known("foo.Bar", 2)
        assert reg.is_known("foo.Baz", 1)

    def test_has_type(self) -> None:
        reg = KnownEventSetRegistry("my_consumer")
        reg.register([EventTypeVersion("foo.Bar", 1)])
        assert reg.has_type("foo.Bar")
        assert not reg.has_type("foo.Baz")

    def test_all_known_returns_frozenset(self) -> None:
        reg = KnownEventSetRegistry("my_consumer")
        reg.register([EventTypeVersion("foo.Bar", 1)])
        known = reg.all_known
        assert isinstance(known, frozenset)
        assert EventTypeVersion("foo.Bar", 1) in known

    def test_multiple_consumers_isolated(self) -> None:
        a = KnownEventSetRegistry("consumer_a")
        b = KnownEventSetRegistry("consumer_b")
        a.register([EventTypeVersion("foo.Bar", 1)])
        assert a.is_known("foo.Bar", 1)
        assert not b.is_known("foo.Bar", 1)
