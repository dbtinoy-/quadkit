import pytest

from uuid import uuid4

from quadkit.events.messages.event import Event
from quadkit.events.projections.base import ProjectionProtocol


class AEvent(Event):
    value: str = "a"


class BEvent(Event):
    value: str = "b"


class MockRegistryHandler:
    def __init__(self):
        self.handled = []

    def can_handle(self, event):
        return isinstance(event, AEvent)

    async def handle_event(self, event):
        self.handled.append(event)


class MockRegistryProjection(ProjectionProtocol):
    def __init__(self):
        super().__init__()
        self.registry_handler = MockRegistryHandler()

    @property
    def name(self) -> str:
        return "test_registry"

    @property
    def handles(self) -> set[type[Event]]:
        return {AEvent, BEvent}

    def _register_event_handlers(self) -> None:
        # register the object-style handler
        self.register_event_handler(self.registry_handler)

    async def reset(self) -> None:
        return None


@pytest.mark.asyncio
async def test_registry_handler_is_invoked_for_matching_event():
    proj = MockRegistryProjection()

    evt = AEvent(aggregate_id=uuid4())
    await proj.apply(evt)

    assert len(proj.registry_handler.handled) == 1
    assert proj.registry_handler.handled[0] is evt


@pytest.mark.asyncio
async def test_registry_handler_not_called_for_non_matching_event():
    proj = MockRegistryProjection()

    evt = BEvent(aggregate_id=uuid4())
    await proj.apply(evt)

    assert proj.registry_handler.handled == []
