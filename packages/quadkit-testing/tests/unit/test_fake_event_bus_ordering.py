"""Unit tests for FakeEventBus.assert_events_in_order (M44)."""

from __future__ import annotations

import pytest

from quadkit.testing.fakes import FakeEventBus


class _UserCreated:
    pass


class _UserDeleted:
    pass


class _EmailSent:
    pass


class TestFakeEventBusEventOrdering:
    """assert_events_in_order validates strict positional event ordering."""

    def _bus(self) -> FakeEventBus:
        return FakeEventBus()

    @pytest.mark.asyncio
    async def test_passes_when_events_match_expected_order(self) -> None:
        bus = self._bus()
        await bus.publish(_UserCreated())
        await bus.publish(_EmailSent())

        # Should not raise
        bus.assert_events_in_order(_UserCreated, _EmailSent)

    @pytest.mark.asyncio
    async def test_raises_on_wrong_order(self) -> None:
        bus = self._bus()
        await bus.publish(_EmailSent())
        await bus.publish(_UserCreated())

        with pytest.raises(AssertionError, match="_UserCreated"):
            bus.assert_events_in_order(_UserCreated, _EmailSent)

    @pytest.mark.asyncio
    async def test_raises_when_not_enough_events_published(self) -> None:
        bus = self._bus()
        await bus.publish(_UserCreated())

        with pytest.raises(AssertionError, match="position 1"):
            bus.assert_events_in_order(_UserCreated, _EmailSent)

    @pytest.mark.asyncio
    async def test_passes_with_single_event(self) -> None:
        bus = self._bus()
        await bus.publish(_UserCreated())

        bus.assert_events_in_order(_UserCreated)

    @pytest.mark.asyncio
    async def test_raises_when_no_events_published(self) -> None:
        bus = self._bus()

        with pytest.raises(AssertionError):
            bus.assert_events_in_order(_UserCreated)

    @pytest.mark.asyncio
    async def test_passes_checking_prefix_of_published_events(self) -> None:
        """Only checks the first N positions — extra events are allowed."""
        bus = self._bus()
        await bus.publish(_UserCreated())
        await bus.publish(_EmailSent())
        await bus.publish(_UserDeleted())

        # Only assert first two
        bus.assert_events_in_order(_UserCreated, _EmailSent)

    @pytest.mark.asyncio
    async def test_clear_resets_published_events(self) -> None:
        bus = self._bus()
        await bus.publish(_UserCreated())
        bus.clear()

        with pytest.raises(AssertionError):
            bus.assert_events_in_order(_UserCreated)
