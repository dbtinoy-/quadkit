"""Unit tests for event projections."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from quadkit.events.messages.event import Event
from quadkit.events.projections.base import (
    InlineProjection,
    ProjectionCheckpoint,
    ProjectionProtocol,
    ProjectionStatus,
)


class _TestEvent(Event):
    """Test event."""

    value: str = "test"


class _TestProjection(ProjectionProtocol):
    """Test projection implementation."""

    def __init__(self):
        super().__init__()
        self.applied_events: list[_TestEvent] = []
        self.reset_called = False

    @property
    def name(self) -> str:
        return "test_projection"

    @property
    def handles(self) -> set[type[Event]]:
        return {_TestEvent}

    async def apply(self, event: Event) -> None:
        if isinstance(event, _TestEvent):
            self.applied_events.append(event)

    async def reset(self) -> None:
        self.reset_called = True
        self.applied_events.clear()


class TestProjectionCheckpoint:
    """Test ProjectionCheckpoint functionality."""

    def test_checkpoint_creation(self):
        """Test creating a checkpoint."""
        checkpoint = ProjectionCheckpoint(
            projection_name="test_proj",
            position=100,
            last_processed_at=datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
            metadata={"key": "value"},
        )

        assert checkpoint.projection_name == "test_proj"
        assert checkpoint.position == 100
        assert checkpoint.last_processed_at == datetime(
            2023, 1, 1, 12, 0, 0, tzinfo=UTC,
        )
        assert checkpoint.metadata == {"key": "value"}

    def test_checkpoint_defaults(self):
        """Test checkpoint default values."""
        checkpoint = ProjectionCheckpoint(projection_name="test")
        assert checkpoint.position == 0
        assert checkpoint.last_processed_at is None
        assert checkpoint.metadata == {}


class TestProjectionBase:
    """Test ProjectionProtocol base functionality."""

    def test_projection_initialization(self):
        """Test projection initialization."""
        proj = _TestProjection()
        assert proj.name == "test_projection"
        assert proj.handles == {_TestEvent}
        assert proj.status == ProjectionStatus.RUNNING
        assert proj.position == 0
        assert proj.checkpoint.projection_name == "test_projection"

    def test_projection_advance(self):
        """Test advancing projection position."""
        proj = _TestProjection()
        proj.advance(50)

        assert proj.position == 50
        assert proj.checkpoint.position == 50
        assert proj.checkpoint.last_processed_at is not None

    def test_projection_can_handle(self):
        """Test checking if projection can handle event."""
        proj = _TestProjection()

        test_event = _TestEvent(aggregate_id=uuid4())
        assert proj.can_handle(test_event)

        class OtherEvent(Event):
            other_data: str

        other_event = OtherEvent(aggregate_id=uuid4(), other_data="test")
        assert not proj.can_handle(other_event)

    def test_projection_status_changes(self):
        """Test projection status changes."""
        proj = _TestProjection()

        assert proj.status == ProjectionStatus.RUNNING

        proj.pause()
        assert proj.status == ProjectionStatus.PAUSED

        proj.resume()
        assert proj.status == ProjectionStatus.RUNNING

        proj.set_error("Test error")
        assert proj.status == ProjectionStatus.ERROR

    @pytest.mark.asyncio
    async def test_projection_apply(self):
        """Test applying events to projection."""
        proj = _TestProjection()
        event = _TestEvent(aggregate_id=uuid4(), value="value1")

        await proj.apply(event)

        assert len(proj.applied_events) == 1
        assert proj.applied_events[0] == event

    @pytest.mark.asyncio
    async def test_projection_reset(self):
        """Test resetting projection."""
        proj = _TestProjection()
        await proj.apply(_TestEvent(aggregate_id=uuid4()))

        assert len(proj.applied_events) == 1

        await proj.reset()
        assert proj.reset_called is True
        assert len(proj.applied_events) == 0


class TestInlineProjection:
    """Test InlineProjection functionality."""

    def test_inline_projection_initialization(self):
        """Test inline projection initialization."""
        proj = InlineProjection("test_inline")

        assert proj.name == "test_inline"
        assert proj.handles == set()
        assert proj._handlers == {}
        assert proj._reset_handler is None

    def test_inline_projection_handle_decorator(self):
        """Test handle decorator."""
        proj = InlineProjection("test")

        @proj.handle(_TestEvent)
        async def handle_test_event(event):
            return f"handled: {event.value}"

        assert _TestEvent in proj.handles
        assert proj._handlers[_TestEvent] == handle_test_event

    def test_inline_projection_on_reset_decorator(self):
        """Test on_reset decorator."""
        proj = InlineProjection("test")

        @proj.on_reset
        async def reset_handler():
            return "reset done"

        assert proj._reset_handler == reset_handler

    @pytest.mark.asyncio
    async def test_inline_projection_apply(self):
        """Test applying events with inline handlers."""
        proj = InlineProjection("test")

        results = []

        @proj.handle(_TestEvent)
        async def handle_test_event(event):
            results.append(f"handled: {event.value}")

        event = _TestEvent(aggregate_id=uuid4(), value="test_value")
        await proj.apply(event)

        assert results == ["handled: test_value"]

    @pytest.mark.asyncio
    async def test_inline_projection_apply_unknown_event(self):
        """Test applying unknown events."""
        proj = InlineProjection("test")

        @proj.handle(_TestEvent)
        async def handle_test_event(event):
            pass

        class OtherEvent(Event):
            other_data: str

        other_event = OtherEvent(aggregate_id=uuid4(), other_data="test")
        # Should not raise error, just do nothing
        await proj.apply(other_event)

    @pytest.mark.asyncio
    async def test_inline_projection_reset(self):
        """Test resetting with inline handler."""
        proj = InlineProjection("test")

        reset_called = False

        @proj.on_reset
        async def reset_handler():
            nonlocal reset_called
            reset_called = True

        await proj.reset()
        assert reset_called is True
