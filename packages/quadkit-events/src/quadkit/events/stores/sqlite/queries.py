"""SQLite query utilities for event stores."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.data.identifiers import Table


class SqliteQueries:
    """SQL query utilities for SQLite event stores."""

    def __init__(self, config: Any) -> None:
        """Initialize with configuration.

        Args:
            config: SQLite configuration object with table names.
        """
        self.config = config
        self._events_table = Table(config.events_table)
        self._snapshots_table = Table(config.snapshots_table)

    def get_create_events_table_sql(self) -> str:
        """Get SQL for creating events table."""
        return f"""
        CREATE TABLE IF NOT EXISTS {self._events_table} (
            global_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            stream_id TEXT NOT NULL,
            stream_version INTEGER NOT NULL,
            event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            event_data TEXT NOT NULL,
            metadata TEXT DEFAULT '{{}}',
            timestamp TEXT NOT NULL,
            UNIQUE(stream_id, stream_version)
        );

        CREATE INDEX IF NOT EXISTS idx_{self._events_table}_stream_id
            ON {self._events_table}(stream_id);
        CREATE INDEX IF NOT EXISTS idx_{self._events_table}_event_type
            ON {self._events_table}(event_type);
        CREATE INDEX IF NOT EXISTS idx_{self._events_table}_timestamp
            ON {self._events_table}(timestamp);
        """

    def get_create_snapshots_table_sql(self) -> str:
        """Get SQL for creating snapshots table."""
        return f"""
        CREATE TABLE IF NOT EXISTS {self._snapshots_table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aggregate_id TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            version INTEGER NOT NULL,
            state TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            UNIQUE(aggregate_id, version)
        );

        CREATE INDEX IF NOT EXISTS idx_{self._snapshots_table}_aggregate_id
            ON {self._snapshots_table}(aggregate_id);
        """

    def get_insert_event_sql(self) -> str:
        """Get SQL for inserting an event."""
        return f"""
        INSERT INTO {self._events_table}
        (stream_id, stream_version, event_id, event_type,
         event_data, metadata, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_read_events_sql(
        self, to_version: int | None = None, limit: int | None = None
    ) -> str:
        """Get SQL for reading events from a stream (M-15)."""
        query = f"""
        SELECT event_id, event_type, event_data, metadata,
               stream_id, stream_version, timestamp
        FROM {self._events_table}
        WHERE stream_id = ? AND stream_version >= ?
        """  # noqa: S608 — table name from validated Table() identifier, never user input
        if to_version is not None:
            query += " AND stream_version <= ?"
        query += " ORDER BY stream_version ASC"
        if limit is not None:
            query += " LIMIT ?"
        return query

    def get_stream_version_sql(self) -> str:
        """Get SQL for getting current stream version."""
        return f"""
        SELECT COALESCE(MAX(stream_version), 0)
        FROM {self._events_table}
        WHERE stream_id = ?
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_stream_all_sql(self) -> str:
        """Get SQL for streaming all events."""
        return f"""
        SELECT global_sequence, event_id, event_type,
               event_data, metadata, stream_id, stream_version, timestamp
        FROM {self._events_table}
        WHERE global_sequence > ?
        ORDER BY global_sequence ASC
        LIMIT ?
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_stream_all_partitioned_sql(self) -> str:
        """Get SQL for streaming all events with partitioning."""
        return f"""
        SELECT global_sequence, event_id, event_type,
               event_data, metadata, stream_id, stream_version, timestamp
        FROM {self._events_table}
        WHERE global_sequence > ?
          AND ABS(STR_HASH(stream_id)) % ? = ?
        ORDER BY global_sequence ASC
        LIMIT ?
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_stream_by_type_sql(self, event_types_count: int) -> str:
        """Get SQL for streaming events by type."""
        placeholders = ",".join("?" * event_types_count)
        return f"""
        SELECT global_sequence, event_id, event_type,
               event_data, metadata, stream_id, stream_version, timestamp
        FROM {self._events_table}
        WHERE global_sequence > ?
          AND event_type IN ({placeholders})
        ORDER BY global_sequence ASC
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def find_by_type_sql(self) -> str:
        """Get SQL for getting events by type."""
        return f"""
        SELECT event_id, event_type, event_data, metadata,
               stream_id, stream_version, timestamp
        FROM {self._events_table}
        WHERE event_type = ?
        ORDER BY global_sequence ASC
        LIMIT ? OFFSET ?
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_events_count_sql(self, stream_id: str | None = None) -> str:
        """Get SQL for counting events."""
        if stream_id:
            return f"""
            SELECT COUNT(*)
            FROM {self._events_table}
            WHERE stream_id = ?
            """  # noqa: S608 — table name from validated Table() identifier, never user input
        return f"SELECT COUNT(*) FROM {self._events_table}"  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_delete_stream_sql(self) -> str:
        """Get SQL for deleting a stream."""
        return f"""
        DELETE FROM {self._events_table}
        WHERE stream_id = ?
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_all_stream_ids_sql(self) -> str:
        """Get SQL for getting all stream IDs."""
        return f"""
        SELECT DISTINCT stream_id
        FROM {self._events_table}
        ORDER BY stream_id
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_insert_snapshot_sql(self) -> str:
        """Get SQL for inserting/updating a snapshot."""
        return f"""
        INSERT OR REPLACE INTO {self._snapshots_table}
        (aggregate_id, aggregate_type, version, state, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_load_snapshot_sql(self) -> str:
        """Get SQL for loading latest snapshot."""
        return f"""
        SELECT aggregate_id, aggregate_type, version, state, timestamp
        FROM {self._snapshots_table}
        WHERE aggregate_id = ?
        ORDER BY version DESC
        LIMIT 1
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_snapshot_by_version_sql(self) -> str:
        """Get SQL for loading specific snapshot version."""
        return f"""
        SELECT aggregate_id, aggregate_type, version, state, timestamp
        FROM {self._snapshots_table}
        WHERE aggregate_id = ? AND version = ?
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_snapshot_count_sql(self) -> str:
        """Get SQL for counting snapshots."""
        return f"""
        SELECT COUNT(*)
        FROM {self._snapshots_table}
        WHERE aggregate_id = ?
        """  # noqa: S608 — table name from validated Table() identifier, never user input

    def get_delete_old_snapshots_sql(self) -> str:
        """Get SQL for deleting old snapshots."""
        return f"""
        DELETE FROM {self._snapshots_table}
        WHERE aggregate_id = ?
          AND version NOT IN (
            SELECT version
            FROM {self._snapshots_table}
            WHERE aggregate_id = ?
            ORDER BY version DESC
            LIMIT ?
          )
        """  # noqa: S608 — table name from validated Table() identifier, never user input


__all__ = ["SqliteQueries"]
