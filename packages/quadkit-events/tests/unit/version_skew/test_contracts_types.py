"""Tests for version-skew contracts types (import + construction only)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class TestEventTypeVersion:
    def test_can_construct(self) -> None:
        from quadkit.contracts.events.version_skew import EventTypeVersion

        t = EventTypeVersion(event_type="foo.Bar", schema_version=1)
        assert t.event_type == "foo.Bar"
        assert t.schema_version == 1
        assert t is not None


class TestUnknownEventTypeReceived:
    def test_can_construct(self) -> None:
        from quadkit.contracts.events.version_skew import (
            UnknownEventTypeReceived,
        )

        alert = UnknownEventTypeReceived(
            consumer_id="my_consumer",
            event_type="foo.Unknown",
            schema_version=1,
            event_id="evt-1",
            tenant_id="t1",
            received_at=datetime.now(timezone.utc),
        )
        assert alert.consumer_id == "my_consumer"
        assert alert.event_type == "foo.Unknown"
        assert alert.schema_version == 1


class TestEventSchemaVersionSkew:
    def test_can_construct(self) -> None:
        from quadkit.contracts.events.version_skew import (
            EventSchemaVersionSkew,
        )

        alert = EventSchemaVersionSkew(
            consumer_id="my_consumer",
            event_type="foo.Bar",
            received_version=3,
            known_versions=frozenset({1, 2}),
            upcast_attempted=True,
            event_id="evt-1",
            tenant_id=None,
            received_at=datetime.now(timezone.utc),
        )
        assert alert.event_type == "foo.Bar"
        assert alert.received_version == 3
        assert alert.known_versions == frozenset({1, 2})
        assert alert.upcast_attempted is True
