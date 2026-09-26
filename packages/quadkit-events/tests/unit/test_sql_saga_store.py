"""Unit tests for SqlSagaStore."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.contracts.data.sql.database import QueryResult
from quadkit.events.sagas.sql import SqlSagaStore, _dict_to_step, _step_to_dict
from quadkit.events.sagas.types import (
    SagaRecord,
    SagaStatus,
    SagaStepRecord,
    SagaStepStatus,
)


def _make_query_result(rows: list[dict] | None = None, row_count: int = 0) -> QueryResult:
    rows = rows or []
    return QueryResult(
        rows=rows,
        row_count=row_count if row_count else len(rows),
        execution_time=0.001,
        success=True,
    )


def _make_saga_row(
    saga_id: str = "saga-1",
    saga_name: str = "order_saga",
    status: str = "pending",
    data: str = "{}",
    steps: str = "{}",
    created_at: str = "2024-01-01T00:00:00",
    updated_at: str = "2024-01-01T00:00:00",
    completed_at: str | None = None,
    error: str | None = None,
) -> dict:
    return {
        "saga_id": saga_id,
        "saga_name": saga_name,
        "status": status,
        "data": data,
        "steps": steps,
        "created_at": created_at,
        "updated_at": updated_at,
        "completed_at": completed_at,
        "error": error,
    }


class TestSqlSagaStore:
    @pytest.fixture
    def mock_db(self) -> MagicMock:
        db = MagicMock(spec=DatabaseProviderProtocol)
        db.execute_query = AsyncMock(return_value=_make_query_result())
        return db

    @pytest.fixture
    def store(self, mock_db: MagicMock) -> SqlSagaStore:
        return SqlSagaStore(db=mock_db)

    @pytest.fixture
    def saga_record(self) -> SagaRecord:
        return SagaRecord(
            saga_id="saga-1",
            saga_name="order_saga",
            status=SagaStatus.PENDING,
            data={"order_id": "ord-1"},
            steps={},
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )

    # ------------------------------------------------------------------
    # initialize
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_initialize_creates_table(self, store: SqlSagaStore, mock_db: MagicMock) -> None:
        await store.initialize()
        assert mock_db.execute_query.await_count >= 1
        calls = [str(call) for call in mock_db.execute_query.call_args_list]
        assert any("CREATE TABLE" in c for c in calls)

    @pytest.mark.asyncio
    async def test_initialize_creates_indexes(self, store: SqlSagaStore, mock_db: MagicMock) -> None:
        await store.initialize()
        calls = [str(call) for call in mock_db.execute_query.call_args_list]
        assert any("CREATE INDEX" in c for c in calls)

    # ------------------------------------------------------------------
    # save — insert
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_save_inserts_new_record(
        self, store: SqlSagaStore, mock_db: MagicMock, saga_record: SagaRecord
    ) -> None:
        # load returns nothing → INSERT path
        mock_db.execute_query = AsyncMock(return_value=_make_query_result())
        await store.save(saga_record)

        calls = mock_db.execute_query.call_args_list
        sqls = [call.args[0] for call in calls]
        assert any("INSERT INTO saga_records" in s for s in sqls)

    # ------------------------------------------------------------------
    # save — update
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_save_updates_existing_record(
        self, store: SqlSagaStore, mock_db: MagicMock, saga_record: SagaRecord
    ) -> None:
        row = _make_saga_row()
        # First call (inside load) returns a row; second call executes UPDATE
        mock_db.execute_query = AsyncMock(
            side_effect=[
                _make_query_result(rows=[row]),  # load
                _make_query_result(),             # UPDATE
            ]
        )
        saga_record.status = SagaStatus.RUNNING
        await store.save(saga_record)

        calls = mock_db.execute_query.call_args_list
        sqls = [call.args[0] for call in calls]
        assert any("UPDATE saga_records" in s for s in sqls)

    # ------------------------------------------------------------------
    # load
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_load_returns_record(
        self, store: SqlSagaStore, mock_db: MagicMock
    ) -> None:
        row = _make_saga_row(status="running")
        mock_db.execute_query = AsyncMock(return_value=_make_query_result(rows=[row]))

        result = await store.load("saga-1")

        assert result is not None
        assert result.saga_id == "saga-1"
        assert result.saga_name == "order_saga"
        assert result.status == SagaStatus.RUNNING

    @pytest.mark.asyncio
    async def test_load_returns_none_when_missing(
        self, store: SqlSagaStore, mock_db: MagicMock
    ) -> None:
        mock_db.execute_query = AsyncMock(return_value=_make_query_result())

        result = await store.load("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_load_deserializes_data(
        self, store: SqlSagaStore, mock_db: MagicMock
    ) -> None:
        row = _make_saga_row(data='{"order_id": "ord-42"}')
        mock_db.execute_query = AsyncMock(return_value=_make_query_result(rows=[row]))

        result = await store.load("saga-1")

        assert result is not None
        assert result.data == {"order_id": "ord-42"}

    @pytest.mark.asyncio
    async def test_load_parses_completed_at(
        self, store: SqlSagaStore, mock_db: MagicMock
    ) -> None:
        row = _make_saga_row(
            status="completed", completed_at="2024-06-15T12:00:00"
        )
        mock_db.execute_query = AsyncMock(return_value=_make_query_result(rows=[row]))

        result = await store.load("saga-1")

        assert result is not None
        assert result.completed_at is not None
        assert result.completed_at.year == 2024

    # ------------------------------------------------------------------
    # list_by_name
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_by_name_returns_records(
        self, store: SqlSagaStore, mock_db: MagicMock
    ) -> None:
        rows = [
            _make_saga_row(saga_id="saga-1"),
            _make_saga_row(saga_id="saga-2"),
        ]
        mock_db.execute_query = AsyncMock(return_value=_make_query_result(rows=rows))

        results = await store.list_by_name("order_saga")

        assert len(results) == 2
        assert results[0].saga_id == "saga-1"
        assert results[1].saga_id == "saga-2"

    @pytest.mark.asyncio
    async def test_list_by_name_returns_empty_when_none(
        self, store: SqlSagaStore, mock_db: MagicMock
    ) -> None:
        mock_db.execute_query = AsyncMock(return_value=_make_query_result())

        results = await store.list_by_name("nonexistent_saga")

        assert results == []

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(
        self, store: SqlSagaStore, mock_db: MagicMock
    ) -> None:
        mock_db.execute_query = AsyncMock(
            return_value=_make_query_result(row_count=1)
        )

        result = await store.delete("saga-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_missing(
        self, store: SqlSagaStore, mock_db: MagicMock
    ) -> None:
        mock_db.execute_query = AsyncMock(
            return_value=_make_query_result(row_count=0)
        )

        result = await store.delete("nonexistent")

        assert result is False

    # ------------------------------------------------------------------
    # step serialization roundtrip
    # ------------------------------------------------------------------

    def test_step_serialization_roundtrip(self) -> None:
        step = SagaStepRecord(
            step_name="charge_payment",
            status=SagaStepStatus.COMPLETED,
            started_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2024, 1, 1, 10, 0, 5, tzinfo=UTC),
            output={"charge_id": "ch_123"},
            error=None,
            attempts=1,
        )

        d = _step_to_dict(step)
        restored = _dict_to_step(d)

        assert restored.step_name == step.step_name
        assert restored.status == step.status
        assert restored.output == step.output
        assert restored.attempts == step.attempts
        assert restored.started_at is not None
        assert restored.completed_at is not None

    def test_step_serialization_roundtrip_with_none_dates(self) -> None:
        step = SagaStepRecord(
            step_name="reserve_stock",
            status=SagaStepStatus.PENDING,
        )

        d = _step_to_dict(step)
        restored = _dict_to_step(d)

        assert restored.step_name == "reserve_stock"
        assert restored.started_at is None
        assert restored.completed_at is None

    @pytest.mark.asyncio
    async def test_load_deserializes_steps(
        self, store: SqlSagaStore, mock_db: MagicMock
    ) -> None:
        from quadkit import serialization as json

        steps_data = {
            "charge_payment": {
                "step_name": "charge_payment",
                "status": "completed",
                "started_at": None,
                "completed_at": None,
                "output": {},
                "error": None,
                "attempts": 1,
            }
        }
        row = _make_saga_row(steps=json.dumps_str(steps_data))
        mock_db.execute_query = AsyncMock(return_value=_make_query_result(rows=[row]))

        result = await store.load("saga-1")

        assert result is not None
        assert "charge_payment" in result.steps
        assert result.steps["charge_payment"].status == SagaStepStatus.COMPLETED

    # ------------------------------------------------------------------
    # updated_at mutation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_save_updates_updated_at(
        self, store: SqlSagaStore, mock_db: MagicMock, saga_record: SagaRecord
    ) -> None:
        original_updated_at = saga_record.updated_at
        mock_db.execute_query = AsyncMock(return_value=_make_query_result())

        await store.save(saga_record)

        assert saga_record.updated_at >= original_updated_at
