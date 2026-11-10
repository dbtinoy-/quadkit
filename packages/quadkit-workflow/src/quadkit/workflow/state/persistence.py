"""State transition persistence implementations for workflow state machines."""

from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING

from quadkit.contracts.workflow import (
    StatePersistenceProtocol,
    StateTransitionRecord,
)
from quadkit.logging import get_logger
from quadkit.workflow.dialect import translate_placeholders
from quadkit.workflow.state.exceptions import StateVersionConflictError

if TYPE_CHECKING:
    from quadkit.contracts.data import DatabaseProviderProtocol

logger = get_logger(__name__)

_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_UNIQUE_VIOLATION_RE = re.compile(
    r"unique|duplicate|constraint|1062|23505", re.IGNORECASE
)


class DatabaseStatePersistence(StatePersistenceProtocol):
    """Database-backed append-only state transition persistence.

    Persists every transition as a row in a transition log table and enforces
    optimistic locking via a monotonic ``version`` column scoped per machine.

    Args:
        provider: Database provider protocol implementation.
        table_name: SQL table used for transition log records.
    """

    def __init__(
        self,
        provider: DatabaseProviderProtocol,
        table_name: str = "workflow_state_transitions",
    ) -> None:
        if not _TABLE_NAME_RE.match(table_name):
            raise ValueError("Invalid table name.")
        self._provider = provider
        self._table_name = table_name
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    def _sql(self, sql: str) -> str:
        """Translate ``?`` placeholders to the provider dialect style."""
        dialect = str(getattr(self._provider, "name", "sqlite"))
        return translate_placeholders(sql, dialect)

    async def append_transition(
        self,
        machine_id: str,
        from_state: str,
        event: str,
        to_state: str,
        expected_version: int,
    ) -> int:
        """Persist a transition and return the new version.

        Raises:
            StateVersionConflictError: A ``RuntimeError`` subclass, raised
                when the persisted version differs from *expected_version*
                (pre-check failure or a concurrent insert winning the
                ``(machine_id, version)`` primary key).
        """
        await self._ensure_schema()

        async with self._provider.transaction():
            current_version = await self.get_current_version(machine_id)
            if current_version != expected_version:
                raise StateVersionConflictError(
                    "Optimistic lock failed: "
                    f"expected={expected_version}, actual={current_version}",
                    expected_version=expected_version,
                    actual_version=current_version,
                )

            next_version = current_version + 1
            now_ts = time.time()
            try:
                await self._provider.execute_insert(
                    self._table_name,
                    {
                        "machine_id": machine_id,
                        "version": next_version,
                        "from_state": from_state,
                        "event": event,
                        "to_state": to_state,
                        "transitioned_at": now_ts,
                    },
                )
            except Exception as exc:  # driver-specific violation types vary
                # A concurrent writer can pass the pre-check and win the
                # insert first; the PK(machine_id, version) collision means
                # the same conflict.  Translate driver-specific uniqueness
                # errors into the typed signal.
                if not _is_unique_violation(exc):
                    raise
                actual_version = await self.get_current_version(machine_id)
                raise StateVersionConflictError(
                    "Optimistic lock failed (concurrent insert): "
                    f"expected={expected_version}, actual={actual_version}",
                    expected_version=expected_version,
                    actual_version=actual_version,
                ) from exc

            logger.debug(
                "state_persistence.transition_appended",
                version=next_version,
            )
            return next_version

    async def load_transitions(self, machine_id: str) -> list[StateTransitionRecord]:
        """Load transitions ordered by version."""
        await self._ensure_schema()
        result = await self._provider.execute_query(
            self._sql(  # noqa: S608 -- table name allowlisted by _TABLE_NAME_RE in __init__
                f"SELECT machine_id, version, from_state, event, to_state, transitioned_at "
                f"FROM {self._table_name} "
                "WHERE machine_id = ? "
                "ORDER BY version ASC"
            ),
            [machine_id],
        )

        records: list[StateTransitionRecord] = []
        for row in result.rows:
            records.append(
                StateTransitionRecord(
                    machine_id=str(row["machine_id"]),
                    version=int(row["version"]),
                    from_state=str(row["from_state"]),
                    event=str(row["event"]),
                    to_state=str(row["to_state"]),
                    transitioned_at=float(row.get("transitioned_at", 0.0)),
                )
            )
        return records

    async def get_current_version(self, machine_id: str) -> int:
        """Return latest version for machine, or ``0`` when absent."""
        await self._ensure_schema()
        result = await self._provider.execute_query(
            self._sql(  # noqa: S608 -- table name allowlisted by _TABLE_NAME_RE in __init__
                f"SELECT COALESCE(MAX(version), 0) AS version "
                f"FROM {self._table_name} "
                "WHERE machine_id = ?"
            ),
            [machine_id],
        )
        if not result.rows:
            return 0
        return int(result.rows[0].get("version", 0) or 0)

    async def _ensure_schema(self) -> None:
        """Create persistence table when it does not exist."""
        if self._schema_ready:
            return
        async with self._schema_lock:
            # Re-check under the lock: another coroutine may have completed
            # the DDL between the first check and the lock acquisition.
            if self._schema_ready:
                return  # type: ignore[unreachable]
            await self._provider.execute(
                f"CREATE TABLE IF NOT EXISTS {self._table_name} ("
                "machine_id TEXT NOT NULL,"
                "version INTEGER NOT NULL,"
                "from_state TEXT NOT NULL,"
                "event TEXT NOT NULL,"
                "to_state TEXT NOT NULL,"
                "transitioned_at DOUBLE PRECISION NOT NULL,"
                "PRIMARY KEY(machine_id, version)"
                ")"
            )
            self._schema_ready = True


def _is_unique_violation(exc: BaseException) -> bool:
    """Best-effort detection of a SQL unique/PK violation.

    Driver exception hierarchies are not uniform (psycopg
    ``UniqueViolation``, SQLAlchemy ``IntegrityError``, sqlite3
    ``IntegrityError``, asyncpg ``UniqueViolation``), so the check looks at
    the type name and the message.
    """
    if "Integrity" in type(exc).__name__ or "Unique" in type(exc).__name__:
        return True
    return bool(_UNIQUE_VIOLATION_RE.search(str(exc)))


__all__ = ["DatabaseStatePersistence"]
