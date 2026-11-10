"""Unit tests for DI event-handler dependency binding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from unittest.mock import MagicMock

import pytest

from quadkit.di import Container
from quadkit.di.markers import Named
from quadkit.events import bind_event_handler, subscribe_event_handlers
from quadkit.events.decorators.handlers import event_handler, get_handler_info
from quadkit.events.messages.event import Event


@dataclass(frozen=True)
class _SampleEvent(Event):
    item_id: str = "x-1"


class _PushService:
    def __init__(self) -> None:
        self.calls: list[str] = []


class _OptionalAudit:
    pass


@pytest.mark.asyncio
async def test_bind_event_handler_zero_extra_params_returns_identity() -> None:
    """Return single-arg event handlers unchanged."""

    @event_handler(_SampleEvent)
    async def on_sample(event: _SampleEvent) -> str:
        return event.item_id

    container = Container()
    bound = await bind_event_handler(on_sample, container)
    assert bound is on_sample


@pytest.mark.asyncio
async def test_bind_event_handler_injects_required_and_optional_dependencies() -> None:
    """Resolve typed container dependencies and pass None for missing optional unions."""

    @event_handler(_SampleEvent, priority=7)
    async def on_sample(
        event: _SampleEvent,
        push: _PushService,
        audit: _OptionalAudit | None = None,
    ) -> tuple[str, _OptionalAudit | None]:
        push.calls.append(event.item_id)
        return event.item_id, audit

    push = _PushService()
    container = Container()
    container.singleton(_PushService, instance=push)

    bound = await bind_event_handler(on_sample, container)
    assert bound is not None
    info = get_handler_info(bound)
    assert info is not None
    assert info.metadata["priority"] == 7

    res = await bound(_SampleEvent(item_id="pet-42"))
    assert res == ("pet-42", None)
    assert push.calls == ["pet-42"]


@pytest.mark.asyncio
async def test_subscribe_event_handlers_skips_missing_required_deps_when_configured() -> (
    None
):
    """Skip handlers whose required DI collaborators are absent when skip_if_missing_deps=True."""

    @event_handler(_SampleEvent)
    async def requires_push(event: _SampleEvent, push: _PushService) -> None:
        push.calls.append(event.item_id)

    @event_handler(_SampleEvent)
    async def event_only(event: _SampleEvent) -> str:
        return event.item_id

    bus = MagicMock()
    container = Container()

    subs = await subscribe_event_handlers(
        bus,
        container,
        [requires_push, event_only],
        skip_if_missing_deps=True,
    )
    assert subs == [(_SampleEvent, event_only)]
    bus.subscribe.assert_called_once_with(_SampleEvent, event_only)


@pytest.mark.asyncio
async def test_bind_event_handler_preserves_annotated_named_qualifier() -> None:
    """DR-30: Annotated[T, Named('maps')] resolves the named registration instead of primary."""

    @event_handler(_SampleEvent)
    async def on_sample(
        event: _SampleEvent,
        maps_push: Annotated[_PushService, Named("maps")],
        primary_push: _PushService,
    ) -> tuple[_PushService, _PushService]:
        maps_push.calls.append(event.item_id)
        return maps_push, primary_push

    primary = _PushService()
    maps = _PushService()
    container = Container()
    container.singleton(_PushService, instance=primary)
    container.singleton(_PushService, instance=maps, name="maps")

    bound = await bind_event_handler(on_sample, container)
    assert bound is not None
    got_maps, got_primary = await bound(_SampleEvent(item_id="vet-99"))
    assert got_maps is maps
    assert got_primary is primary
    assert maps.calls == ["vet-99"]
    assert primary.calls == []
