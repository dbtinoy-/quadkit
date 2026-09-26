"""Generic AppendLogProtocol implementation using DatabaseService.

This module provides an implementation of the AppendLogProtocol protocol
that uses the unified DatabaseService to perform append-only
storage operations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

from quadkit import serialization as json
from quadkit.contracts import DatabaseProviderProtocol
from quadkit.contracts.data.sql.append_log import AppendLogProtocol
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import DatabaseConnectionError, DatabaseError, QueryError

T = TypeVar("T")

_ROW_COLUMNS = (
    "event_id",
    "event_type",
    "event_data",
    "metadata",
    "timestamp",
    "stream_version",
)


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Normalize a driver row (mapping-like or positional) to a field dict."""
    if hasattr(row, "keys"):
        return dict(row)
    return dict(zip(_ROW_COLUMNS, tuple(row), strict=False))


class DatabaseProviderAppendLog(AppendLogProtocol[T], Generic[T]):
    """Append log implementation backed by DatabaseService.

    Uses standard SQL queries executed through the provider, keeping raw SQL
    contained within the database package.
    """

    def __init__(
        self,
        provider: DatabaseProviderProtocol,
        table_name: str,
        serializer: Callable[[T], dict[str, Any]],
        deserializer: Callable[[dict[str, Any]], T],
    ):
        self.provider = provider
        self.table_name = table_name
        self._serialize = serializer
        self._deserialize = deserializer

    async def append(
        self, stream_id: str, events: list[T], expected_version: int | None = None
    ) -> int:
        """Append events to a stream."""
        if not events:
            return await self.get_stream_version(stream_id)

        # Check optimistic concurrency
        current_version = await self.get_stream_version(stream_id)
        if expected_version is not None and current_version != expected_version:
            raise ValueError(
                f"Concurrency conflict: expected version {expected_version}, "
                f"but stream '{stream_id}' is at version {current_version}",
            )

        new_version = current_version

        # Some providers don't natively return sequences on INSERT without RETURNING,
        # but we can do a manual transaction. `provider.transaction()` is used by the caller
        # or we manage it here.

        for i, event in enumerate(events):
            version = current_version + i + 1
            data = self._serialize(event)

            # Extract standard fields if they exist in the serialized data,
            # otherwise formulate them.
            event_id = data.get("event_id", data.get("id"))
            event_type = data.get("event_type", type(event).__name__)
            metadata = data.get("metadata", {})
            timestamp = data.get(
                "timestamp",
                data.get(
                    "created_at",
                    ambient_clock.now(),
                ),
            )

            # Using raw SQL string BUT securely via provider parameters, and strictly within the DB package
            query = f"""
                INSERT INTO {self.table_name} 
                (stream_id, stream_version, event_id, event_type, event_data, metadata, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """  # noqa: S608 -- self.table_name set at init from caller config, values parameterized
            await self.provider.execute_query(
                query,
                [
                    stream_id,
                    version,
                    event_id,
                    event_type,
                    json.dumps(data),
                    json.dumps(metadata),
                    timestamp,
                ],
            )
            new_version = version

        return new_version

    async def read(
        self, stream_id: str, from_version: int = 0, to_version: int | None = None
    ) -> list[T]:
        """Read events from a stream."""
        query = f"""
            SELECT event_id, event_type, event_data, metadata, timestamp, stream_version
            FROM {self.table_name}
            WHERE stream_id = $1 AND stream_version >= $2
        """  # noqa: S608 -- self.table_name set at init from caller config, values parameterized
        params: list[Any] = [stream_id, from_version]

        if to_version is not None:
            query += " AND stream_version <= $3"
            params.append(to_version)

        query += " ORDER BY stream_version ASC"

        rows = await self.provider.execute_query(query, params)
        if not rows:
            return []

        # Parse rows
        results = []
        for row in rows:
            # row is typically a dict-like object from advanced providers,
            # or a tuple. Make it play nice.
            row_dict = _row_to_dict(row)

            data = row_dict["event_data"]
            if isinstance(data, str):
                data = json.loads(data)

            # Allow deserializer to utilize full row data if needed
            data["_raw_row"] = row_dict
            results.append(self._deserialize(data))

        return results

    async def read_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        """Read all events."""
        query = f"""
            SELECT event_id, event_type, event_data, metadata, timestamp, stream_version
            FROM {self.table_name}
            ORDER BY global_sequence ASC
            LIMIT $1 OFFSET $2
        """  # noqa: S608 -- self.table_name set at init from caller config, values parameterized
        rows = await self.provider.execute_query(query, [limit, offset])
        if not rows:
            return []

        results = []
        for row in rows:
            row_dict = _row_to_dict(row)
            data = row_dict["event_data"]
            if isinstance(data, str):
                data = json.loads(data)
            data["_raw_row"] = row_dict
            results.append(self._deserialize(data))
        return results

    async def get_stream_version(self, stream_id: str) -> int:
        """Get the current stream version."""
        query = f"""
            SELECT COALESCE(MAX(stream_version), 0)
            FROM {self.table_name}
            WHERE stream_id = $1
        """  # noqa: S608 -- self.table_name set at init from caller config, values parameterized
        result = await self.provider.execute_query(query, [stream_id])
        if not result:
            return 0
        row = result[0]
        return cast("int", row.get("coalesce", row.get("max", 0)))

    async def delete_stream(self, stream_id: str) -> bool:
        """Delete all events in a stream."""
        query = f"DELETE FROM {self.table_name} WHERE stream_id = $1"  # noqa: S608 -- self.table_name set at init from caller config, values parameterized
        try:
            await self.provider.execute_query(query, [stream_id])
            return True
        except (DatabaseError, QueryError, DatabaseConnectionError) as e:
            import logging

            logging.getLogger(__name__).debug("Append log trim: %s", e)
            return False

    async def count(self, stream_id: str | None = None) -> int:
        """Count events."""
        if stream_id:
            query = f"SELECT COUNT(*) FROM {self.table_name} WHERE stream_id = $1"  # noqa: S608 -- self.table_name set at init from caller config, values parameterized
            params = [stream_id]
        else:
            query = f"SELECT COUNT(*) FROM {self.table_name}"  # noqa: S608 -- self.table_name set at init from caller config, values parameterized
            params = []

        result = await self.provider.execute_query(query, params)
        if not result:
            return 0
        row = result[0]
        return cast("int", row.get("count", 0))


__all__ = ["DatabaseProviderAppendLog"]
