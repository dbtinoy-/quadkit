"""SQL-backed saga store using DatabaseProviderProtocol."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from quadkit import serialization as json
from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.events.sagas.store import SagaStore
from quadkit.events.sagas.types import (
    SagaRecord,
    SagaStatus,
    SagaStepRecord,
    SagaStepStatus,
)
from quadkit.logging import get_logger
from quadkit.primitives import clock

__all__ = ["SqlSagaStore"]

_DDL = """
CREATE TABLE IF NOT EXISTS saga_records (
    saga_id       VARCHAR(255) PRIMARY KEY,
    saga_name     VARCHAR(255) NOT NULL,
    status        VARCHAR(50)  NOT NULL DEFAULT 'pending',
    data          TEXT         NOT NULL DEFAULT '{}',
    steps         TEXT         NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at  TIMESTAMP,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_saga_name ON saga_records(saga_name);
CREATE INDEX IF NOT EXISTS idx_saga_status ON saga_records(status)
"""


def _step_to_dict(step: SagaStepRecord) -> dict[str, Any]:
    return {
        "step_name": step.step_name,
        "status": step.status.value,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
        "output": step.output,
        "error": step.error,
        "attempts": step.attempts,
    }


def _naive_utc(dt: datetime | None) -> datetime | None:
    """Normalize to a naive UTC datetime for TIMESTAMP columns."""
    if dt is None:
        return None
    return dt if dt.tzinfo is None else dt.astimezone(UTC).replace(tzinfo=None)


def _dict_to_step(d: dict[str, Any]) -> SagaStepRecord:
    def _dt(val: Any) -> datetime | None:
        if val is None:
            return None
        return val if isinstance(val, datetime) else datetime.fromisoformat(val)

    return SagaStepRecord(
        step_name=d["step_name"],
        status=SagaStepStatus(d["status"]),
        started_at=_dt(d.get("started_at")),
        completed_at=_dt(d.get("completed_at")),
        output=d.get("output", {}),
        error=d.get("error"),
        attempts=d.get("attempts", 0),
    )


class SqlSagaStore(SagaStore):
    """SQL-backed saga store for durable saga state persistence.

    Stores saga records in a relational database via DatabaseProviderProtocol.
    Complex fields (data, steps) are JSON-serialized.

    Args:
        db: Database provider for executing queries.
    """

    def __init__(self, db: DatabaseProviderProtocol) -> None:
        self._db = db
        self._logger = get_logger(__name__)

    async def initialize(self) -> None:
        """Create the saga_records table and indexes if they do not exist."""
        for stmt in _DDL.split(";"):
            stmt = stmt.strip()
            if stmt:
                await self._db.execute_query(stmt, [])
        self._logger.info("saga_records_table_initialized")

    async def save(self, record: SagaRecord) -> None:
        """Persist or update a saga record.

        Args:
            record: The saga record to save.
        """
        record.updated_at = clock.now()
        steps_json = json.dumps_str(
            {name: _step_to_dict(step) for name, step in record.steps.items()}
        )
        data_json = json.dumps_str(record.data)

        existing = await self.load(record.saga_id)
        if existing is not None:
            sql = (
                "UPDATE saga_records SET saga_name=?, status=?, data=?, steps=?, "
                "updated_at=?, completed_at=?, error=? WHERE saga_id=?"
            )
            params: list[Any] = [
                record.saga_name,
                record.status.value,
                data_json,
                steps_json,
                _naive_utc(record.updated_at),
                _naive_utc(record.completed_at),
                record.error,
                record.saga_id,
            ]
        else:
            sql = (
                "INSERT INTO saga_records (saga_id, saga_name, status, data, steps, "
                "created_at, updated_at, completed_at, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            params = [
                record.saga_id,
                record.saga_name,
                record.status.value,
                data_json,
                steps_json,
                _naive_utc(record.created_at),
                _naive_utc(record.updated_at),
                _naive_utc(record.completed_at),
                record.error,
            ]
        await self._db.execute_query(sql, params)

    async def load(self, saga_id: str) -> SagaRecord | None:
        """Load a saga record by ID.

        Args:
            saga_id: The saga identifier to look up.

        Returns:
            The matching SagaRecord, or None if not found.
        """
        result = await self._db.execute_query(
            "SELECT * FROM saga_records WHERE saga_id = ? LIMIT 1", [saga_id]
        )
        if not result.rows:
            return None
        return self._row_to_record(result.rows[0])

    async def list_by_name(self, saga_name: str) -> list[SagaRecord]:
        """List all sagas with a given name, newest first.

        Args:
            saga_name: The saga name to filter by.

        Returns:
            List of matching SagaRecord instances ordered by created_at DESC.
        """
        result = await self._db.execute_query(
            "SELECT * FROM saga_records WHERE saga_name = ? ORDER BY created_at DESC",
            [saga_name],
        )
        return [self._row_to_record(row) for row in result.rows]

    async def delete(self, saga_id: str) -> bool:
        """Delete a saga record by ID.

        Args:
            saga_id: The saga identifier to delete.

        Returns:
            True if the record was deleted, False if it did not exist.
        """
        result = await self._db.execute_query(
            "DELETE FROM saga_records WHERE saga_id = ?", [saga_id]
        )
        return result.row_count > 0

    def _row_to_record(self, row: dict[str, Any]) -> SagaRecord:
        raw_steps = json.loads_str(row.get("steps", "{}"))
        steps = {name: _dict_to_step(d) for name, d in raw_steps.items()}
        data = json.loads_str(row.get("data", "{}"))

        def _parse_dt(val: Any) -> datetime:
            return val if isinstance(val, datetime) else datetime.fromisoformat(val)

        def _parse_dt_opt(val: Any) -> datetime | None:
            return None if val is None else _parse_dt(val)

        return SagaRecord(
            saga_id=row["saga_id"],
            saga_name=row["saga_name"],
            status=SagaStatus(row["status"]),
            data=data,
            steps=steps,
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            completed_at=_parse_dt_opt(row.get("completed_at")),
            error=row.get("error"),
        )
