from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from quadkit.sql.outbox.store import SQLOutboxStore
from quadkit.contracts.domain.events import DomainEvent
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    order_id: str = ""
    occurred_at: datetime = None


class TestSQLOutboxStore:

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        db = MagicMock()
        db.execute = AsyncMock(return_value=None)
        db.fetch_all = AsyncMock(return_value=[])
        return db

    @pytest.fixture
    def store(self, mock_db: MagicMock) -> SQLOutboxStore:
        return SQLOutboxStore(db=mock_db, table="outbox_events")

    @pytest.mark.asyncio
    async def test_append_batch_inserts_events(self, store: SQLOutboxStore, mock_db: MagicMock) -> None:
        events = [OrderPlaced(order_id="o1", occurred_at=datetime.now())]
        await store.append_batch(events)
        mock_db.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_fetch_pending_returns_undelivered_events(
        self, store: SQLOutboxStore, mock_db: MagicMock
    ) -> None:
        mock_db.fetch_all = AsyncMock(return_value=[
            {"id": "1", "payload": '{"order_id": "o1"}', "event_type": "OrderPlaced", "status": "pending"},
        ])
        rows = await store.fetch_pending(limit=10)
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_mark_delivered_updates_status(
        self, store: SQLOutboxStore, mock_db: MagicMock
    ) -> None:
        await store.mark_delivered("event-id-1")
        mock_db.execute.assert_awaited()
