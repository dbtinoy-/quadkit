"""Database-backed content-addressed checkpoint store.

Uses ``DatabaseProviderProtocol`` from ``quadkit-contracts`` to persist
content-addressed checkpoint entries in a SQL table.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
import re
import time
from typing import TYPE_CHECKING, Any

from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
)
from quadkit.serialization import dumps, loads
from quadkit.workflow.dialect import translate_placeholders

if TYPE_CHECKING:
    from quadkit.contracts.data.sql.database import DatabaseProviderProtocol

_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

__all__ = ["DatabaseContentCheckpointStore"]


def _entry_to_json(entry: ContentCheckpointEntry) -> str:
    d = asdict(entry)
    d["completed_at"] = entry.completed_at.isoformat()
    payload = dumps(d)
    return payload.decode() if isinstance(payload, bytes) else payload


def _entry_from_json(data: dict[str, Any]) -> ContentCheckpointEntry:
    data = dict(data)
    data["completed_at"] = datetime.fromisoformat(data["completed_at"])
    return ContentCheckpointEntry(**data)


class DatabaseContentCheckpointStore:
    """Content-addressed checkpoint store backed by a SQL database.

    Creates a ``workflow_content_checkpoints`` table with columns
    ``key_str`` (PK), ``entry_json``, ``stage_handler_version``,
    ``output_size_bytes``, ``completed_at``, and ``created_at``.
    """

    def __init__(
        self,
        provider: DatabaseProviderProtocol,
        table_name: str = "workflow_content_checkpoints",
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

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._schema_lock:
            # Re-check under the lock: another coroutine may have completed
            # the DDL between the first check and the lock acquisition.
            if self._schema_ready:
                return  # type: ignore[unreachable]
            await self._provider.execute(
                f"CREATE TABLE IF NOT EXISTS {self._table_name} ("
                "key_str TEXT PRIMARY KEY,"
                "entry_json TEXT NOT NULL,"
                "stage_handler_version TEXT NOT NULL,"
                "output_size_bytes INTEGER NOT NULL,"
                "completed_at TEXT NOT NULL,"
                "created_at DOUBLE PRECISION NOT NULL"
                ")"
            )
            self._schema_ready = True

    async def get(self, key: ContentCheckpointKey) -> ContentCheckpointEntry | None:
        await self._ensure_schema()
        result = await self._provider.execute_query(
            self._sql(  # noqa: S608 -- table name allowlisted by _TABLE_NAME_RE in __init__
                f"SELECT key_str, entry_json FROM {self._table_name} WHERE key_str = ?"
            ),
            [key.as_str()],
        )
        if not result.rows:
            return None
        row = result.rows[0]
        raw = row.get("entry_json", "{}")
        data = loads(raw)
        if not isinstance(data, dict):
            return None
        return _entry_from_json(data)

    async def set(
        self, key: ContentCheckpointKey, entry: ContentCheckpointEntry
    ) -> None:
        """Set a checkpoint entry, using ON CONFLICT DO NOTHING for safety.

        If two concurrent sagas race to set the same key, the second insert
        is silently ignored — content-addressed checkpoints are deterministic,
        so the output is identical regardless of which saga's insert wins.
        """
        await self._ensure_schema()
        entry_json = _entry_to_json(entry)
        now_ts = time.time()
        await self._provider.execute(
            self._sql(  # noqa: S608 -- table name allowlisted by _TABLE_NAME_RE in __init__
                f"INSERT INTO {self._table_name} "
                f"(key_str, entry_json, stage_handler_version, "
                f"output_size_bytes, completed_at, created_at) "
                f"VALUES (?, ?, ?, ?, ?, ?) "
                f"ON CONFLICT (key_str) DO NOTHING"
            ),
            [
                key.as_str(),
                entry_json,
                entry.stage_handler_version,
                entry.output_size_bytes,
                entry.completed_at.isoformat(),
                now_ts,
            ],
        )

    async def evict(self, key: ContentCheckpointKey) -> None:
        await self._ensure_schema()
        await self._provider.execute_delete(
            self._table_name,
            self._sql("key_str = ?"),
            [key.as_str()],
        )

    async def list_by_stage(
        self,
        stage_id: str,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> Sequence[ContentCheckpointKey]:
        await self._ensure_schema()
        where_parts = ["key_str LIKE ?"]
        params: list[Any] = [f"{stage_id}|%"]
        if tenant_id is not None:
            where_parts.append("key_str LIKE ?")
            params.append(f"{stage_id}|{tenant_id}|%")
        where = " AND ".join(where_parts)
        params.append(limit)
        result = await self._provider.execute_query(
            self._sql(  # noqa: S608 -- table name allowlisted by _TABLE_NAME_RE in __init__
                f"SELECT key_str FROM {self._table_name} WHERE {where} LIMIT ?"
            ),
            params,
        )
        keys: list[ContentCheckpointKey] = []
        for row in result.rows:
            raw = row.get("key_str", "")
            parts = raw.split("|", 3)
            if len(parts) >= 4:
                keys.append(
                    ContentCheckpointKey(
                        stage_id=parts[0],
                        tenant_id=parts[1] if parts[1] != "_global" else None,
                        input_hash=bytes.fromhex(parts[2]),
                        config_hash=bytes.fromhex(parts[3]),
                    )
                )
        return keys
