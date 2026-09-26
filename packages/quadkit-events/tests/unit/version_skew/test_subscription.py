"""Tests for VersionAwareSubscription."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.events.version_skew import EventTypeVersion
from quadkit.events.version_skew import KnownEventSetRegistry
from quadkit.events.version_skew.subscription import VersionAwareSubscription


@pytest.fixture
def bus() -> MagicMock:
    b = MagicMock()
    b.subscribe = MagicMock()
    return b


@pytest.fixture
def evolution() -> MagicMock:
    e = MagicMock()
    e.get_migration_path = AsyncMock(return_value=None)
    e.migrate_data = AsyncMock(return_value={})
    return e


@pytest.fixture
def alert_dispatcher() -> MagicMock:
    a = MagicMock()
    a.send_alert = AsyncMock()
    return a


@pytest.fixture
def handler() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def known_set() -> KnownEventSetRegistry:
    reg = KnownEventSetRegistry("my_consumer")
    reg.register([
        EventTypeVersion("test.OrderPlaced", 1),
        EventTypeVersion("test.OrderPlaced", 2),
    ])
    return reg


class TestVersionAwareSubscription:
    @pytest.mark.asyncio
    async def test_known_version_invokes_handler(
        self, bus, evolution, alert_dispatcher, handler, known_set,
    ) -> None:
        sub = VersionAwareSubscription(
            consumer_id="my_consumer",
            bus=bus,
            known_set=known_set,
            evolution=evolution,
            alert_dispatcher=alert_dispatcher,
        )
        envelope = _make_envelope(event_type="test.OrderPlaced", version=1)
        await sub._handle(envelope, handler)
        handler.assert_awaited_once_with(envelope)
        alert_dispatcher.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_type_fires_alert(
        self, bus, evolution, alert_dispatcher, handler, known_set,
    ) -> None:
        sub = VersionAwareSubscription(
            consumer_id="my_consumer",
            bus=bus,
            known_set=known_set,
            evolution=evolution,
            alert_dispatcher=alert_dispatcher,
        )
        envelope = _make_envelope(event_type="test.UnknownType", version=1)
        await sub._handle(envelope, handler)
        handler.assert_not_called()
        alert_dispatcher.send_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_version_without_upcast_fires_alert(
        self, bus, evolution, alert_dispatcher, handler, known_set,
    ) -> None:
        sub = VersionAwareSubscription(
            consumer_id="my_consumer",
            bus=bus,
            known_set=known_set,
            evolution=evolution,
            alert_dispatcher=alert_dispatcher,
        )
        envelope = _make_envelope(event_type="test.OrderPlaced", version=3)
        await sub._handle(envelope, handler)
        handler.assert_not_called()
        alert_dispatcher.send_alert.assert_awaited_once()
        call_args = alert_dispatcher.send_alert.call_args[1]
        assert "skew" in call_args.get("title", "").lower()

    @pytest.mark.asyncio
    async def test_unknown_version_with_upcast_invokes_handler(
        self, bus, evolution, alert_dispatcher, handler, known_set,
    ) -> None:
        evolution.get_migration_path.return_value = MagicMock()
        sub = VersionAwareSubscription(
            consumer_id="my_consumer",
            bus=bus,
            known_set=known_set,
            evolution=evolution,
            alert_dispatcher=alert_dispatcher,
        )
        envelope = _make_envelope(event_type="test.OrderPlaced", version=3)
        await sub._handle(envelope, handler)
        handler.assert_awaited_once()
        alert_dispatcher.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_evolution_skips_upcast_attempt(
        self, bus, alert_dispatcher, handler, known_set,
    ) -> None:
        sub = VersionAwareSubscription(
            consumer_id="my_consumer",
            bus=bus,
            known_set=known_set,
            evolution=None,
            alert_dispatcher=alert_dispatcher,
        )
        envelope = _make_envelope(event_type="test.OrderPlaced", version=3)
        await sub._handle(envelope, handler)
        handler.assert_not_called()
        alert_dispatcher.send_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tolerant_reader_extra_fields_ok(
        self, bus, evolution, alert_dispatcher, handler, known_set,
    ) -> None:
        sub = VersionAwareSubscription(
            consumer_id="my_consumer",
            bus=bus,
            known_set=known_set,
            evolution=evolution,
            alert_dispatcher=alert_dispatcher,
        )
        envelope = _make_envelope(event_type="test.OrderPlaced", version=2, extra="ignored")
        await sub._handle(envelope, handler)
        handler.assert_awaited_once()
        alert_dispatcher.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_version_upcasts_to_latest_known_version(
        self, bus, alert_dispatcher, handler,
    ) -> None:
        """Migration from older version to latest known version."""
        from quadkit.events.schema.evolution import SchemaEvolution, Upcaster
        from unittest.mock import MagicMock

        class TestUpcaster(Upcaster):
            event_type = "test.OrderPlaced"
            source_version = 1
            target_version = 2

            async def upcast(self, data: dict) -> dict:
                data["upcasted"] = True
                return data

        registry = MagicMock()
        evolution = SchemaEvolution(registry)
        evolution.register_upcaster(TestUpcaster())

        known_set = KnownEventSetRegistry("my_consumer")
        known_set.register([EventTypeVersion("test.OrderPlaced", 2)])

        sub = VersionAwareSubscription(
            consumer_id="my_consumer",
            bus=bus,
            known_set=known_set,
            evolution=evolution,
            alert_dispatcher=alert_dispatcher,
        )

        envelope = _make_envelope(event_type="test.OrderPlaced", version=1)
        await sub._handle(envelope, handler)

        handler.assert_awaited_once()
        alert_dispatcher.send_alert.assert_not_called()
        assert envelope.version == 2
        assert envelope.event_data.get("upcasted") is True

    @pytest.mark.asyncio
    async def test_subscribe_delegates_to_bus(
        self, bus, evolution, alert_dispatcher, handler, known_set,
    ) -> None:
        sub = VersionAwareSubscription(
            consumer_id="my_consumer",
            bus=bus,
            known_set=known_set,
            evolution=evolution,
            alert_dispatcher=alert_dispatcher,
        )
        await sub.subscribe("test.OrderPlaced", handler)
        bus.subscribe.assert_called_once()


def _make_envelope(event_type: str, version: int, **extra: Any) -> MagicMock:
    env = MagicMock()
    env.event_type = event_type
    env.version = version
    env.event_id = "evt-123"
    env.metadata = {}
    env.timestamp = datetime.now(timezone.utc)
    env.event_data = {"foo": "bar", **extra}
    return env
