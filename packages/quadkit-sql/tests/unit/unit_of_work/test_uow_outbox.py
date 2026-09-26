"""Tests for AbstractUnitOfWork outbox integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.data.outbox import OutboxStoreProtocol
from quadkit.contracts.domain.events import DomainEvent
from quadkit.domain.unit_of_work import AbstractUnitOfWork


class _ConcreteUoW(AbstractUnitOfWork):
    """Minimal concrete UoW for testing — flush is a no-op."""

    async def _flush(self) -> None:
        pass


class _SimpleEvent(DomainEvent):
    pass


class TestUnitOfWorkOutboxIntegration:
    @pytest.fixture
    def mock_outbox(self) -> MagicMock:
        store = MagicMock(spec=OutboxStoreProtocol)
        store.append_batch = AsyncMock()
        return store

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        bus = MagicMock()
        bus.publish = AsyncMock()
        return bus

    # ------------------------------------------------------------------
    # Outbox-enabled path
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_commit_with_outbox_writes_events_to_outbox(
        self, mock_outbox: MagicMock
    ) -> None:
        uow = _ConcreteUoW(outbox_store=mock_outbox)
        event = _SimpleEvent()
        uow.register_event(event)
        await uow.commit()
        mock_outbox.append_batch.assert_awaited_once()
        args, _ = mock_outbox.append_batch.call_args
        assert event in args[0]

    @pytest.mark.asyncio
    async def test_commit_with_outbox_does_not_publish_directly(
        self, mock_outbox: MagicMock, mock_event_bus: MagicMock
    ) -> None:
        uow = _ConcreteUoW(outbox_store=mock_outbox, event_bus=mock_event_bus)
        uow.register_event(_SimpleEvent())
        await uow.commit()
        # outbox takes over — direct bus publish must NOT be called
        mock_event_bus.publish.assert_not_awaited()
        mock_outbox.append_batch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_commit_with_no_events_does_not_call_outbox(
        self, mock_outbox: MagicMock
    ) -> None:
        uow = _ConcreteUoW(outbox_store=mock_outbox)
        await uow.commit()
        mock_outbox.append_batch.assert_not_awaited()

    # ------------------------------------------------------------------
    # Fallback path (no outbox)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_commit_without_outbox_publishes_directly(
        self, mock_event_bus: MagicMock
    ) -> None:
        uow = _ConcreteUoW(event_bus=mock_event_bus)
        uow.register_event(_SimpleEvent())
        await uow.commit()
        mock_event_bus.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_commit_without_outbox_no_event_bus_is_noop(self) -> None:
        """No outbox, no event bus — commit must still succeed silently."""
        uow = _ConcreteUoW()
        uow.register_event(_SimpleEvent())
        await uow.commit()  # no assertions — just must not raise

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_context_manager_commits_on_success(
        self, mock_outbox: MagicMock
    ) -> None:
        async with _ConcreteUoW(outbox_store=mock_outbox) as uow:
            uow.register_event(_SimpleEvent())
        mock_outbox.append_batch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_manager_rollback_on_exception_skips_outbox(
        self, mock_outbox: MagicMock
    ) -> None:
        async def _run() -> None:
            async with _ConcreteUoW(outbox_store=mock_outbox) as uow:
                uow.register_event(_SimpleEvent())
                raise RuntimeError("domain error")

        with pytest.raises(RuntimeError):
            await _run()
        mock_outbox.append_batch.assert_not_awaited()
