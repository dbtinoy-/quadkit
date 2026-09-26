from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.result import Ok


class TestOutboxPublisher:

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        store = MagicMock()
        store.fetch_pending = AsyncMock(return_value=[])
        store.mark_delivered = AsyncMock()
        store.mark_failed = AsyncMock()
        return store

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        bus = MagicMock()
        bus.publish_raw = AsyncMock(return_value=Ok(None))
        return bus

    @pytest.mark.asyncio
    async def test_process_batch_publishes_and_marks_delivered(
        self, mock_store: MagicMock, mock_event_bus: MagicMock
    ) -> None:
        from quadkit.sql.outbox.publisher import OutboxPublisher

        mock_store.fetch_pending = AsyncMock(return_value=[
            {"id": "1", "payload": '{"order_id": "o1"}', "event_type": "OrderPlaced"}
        ])
        publisher = OutboxPublisher(store=mock_store, event_bus=mock_event_bus)
        count = await publisher._process_batch()
        assert count == 1
        mock_event_bus.publish_raw.assert_awaited_once()
        mock_store.mark_delivered.assert_awaited_once_with("1")

    @pytest.mark.asyncio
    async def test_process_batch_marks_failed_on_bus_error(
        self, mock_store: MagicMock, mock_event_bus: MagicMock
    ) -> None:
        from quadkit.sql.outbox.publisher import OutboxPublisher

        mock_store.fetch_pending = AsyncMock(return_value=[
            {"id": "2", "payload": '{"order_id": "o2"}', "event_type": "OrderPlaced"}
        ])
        mock_event_bus.publish_raw = AsyncMock(side_effect=RuntimeError("bus down"))
        publisher = OutboxPublisher(store=mock_store, event_bus=mock_event_bus)
        await publisher._process_batch()
        mock_store.mark_failed.assert_awaited_once()
        mock_store.mark_delivered.assert_not_awaited()
