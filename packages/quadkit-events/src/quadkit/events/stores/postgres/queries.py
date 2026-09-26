"""PostgreSQL SQL query templates."""

from __future__ import annotations

from enum import Enum


class PostgresQueries(str, Enum):
    """SQL query templates for PostgreSQL stores."""

    # Event Store Queries
    GET_STREAM_VERSION = """
        SELECT COALESCE(MAX(stream_version), 0) AS version
        FROM {table}
        WHERE stream_id = $1
    """

    INSERT_EVENT = """
        INSERT INTO {table}
        (stream_id, stream_version, event_id, event_type,
         event_data, metadata, timestamp)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
    """

    READ_STREAM = """
        SELECT event_id, event_type, event_data, metadata,
               stream_id, stream_version, timestamp
        FROM {table}
        WHERE stream_id = $1 AND stream_version >= $2
          AND ($3::int IS NULL OR stream_version <= $3)
        ORDER BY stream_version ASC
    """

    STREAM_ALL = """
        SELECT global_sequence, event_id, event_type,
               event_data, metadata, stream_id, stream_version, timestamp
        FROM {table}
        WHERE global_sequence > $1
        ORDER BY global_sequence ASC
        LIMIT $2
    """

    STREAM_ALL_PARTITIONED = """
        SELECT global_sequence, event_id, event_type,
               event_data, metadata, stream_id, stream_version, timestamp
        FROM {table}
        WHERE global_sequence > $1
          AND ABS(HASHTEXT(stream_id)) % $3 = $4
        ORDER BY global_sequence ASC
        LIMIT $2
    """

    GET_STORED_SINCE = """
        SELECT global_sequence, stream_id, stream_version,
               event_id, event_type, event_data, metadata, timestamp
        FROM {table}
        WHERE global_sequence > $1
        ORDER BY global_sequence ASC
        LIMIT $2
    """

    STREAM_BY_TIMESTAMP = """
        SELECT global_sequence, event_id, event_type,
               event_data, metadata, timestamp
        FROM {table}
        WHERE timestamp >= $1 AND global_sequence > $2
        LIMIT $3
    """

    STREAM_BY_TYPE = """
        SELECT global_sequence, event_id, event_type,
               event_data, metadata, stream_id, stream_version, timestamp
        FROM {table}
        WHERE global_sequence > $1 AND event_type = ANY($2)
        ORDER BY global_sequence ASC
    """

    GET_BY_TYPE_PAGED = """
        SELECT event_id, event_type, event_data, metadata,
               stream_id, stream_version, timestamp
        FROM {table}
        WHERE event_type = $1
        ORDER BY global_sequence ASC
        LIMIT $2 OFFSET $3
    """

    # Snapshot Store Queries
    INSERT_SNAPSHOT = """
        INSERT INTO {table}
        (aggregate_id, aggregate_type, version, state, timestamp)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (aggregate_id, version) DO UPDATE
        SET state = $4, timestamp = $5
    """

    GET_LATEST_SNAPSHOT = """
        SELECT aggregate_id, aggregate_type, version, state, timestamp
        FROM {table}
        WHERE aggregate_id = $1
        ORDER BY version DESC
        LIMIT 1
    """

    GET_SNAPSHOT_BY_VERSION = """
        SELECT aggregate_id, aggregate_type, version, state, timestamp
        FROM {table}
        WHERE aggregate_id = $1 AND version = $2
    """

    DELETE_SNAPSHOTS = """
        DELETE FROM {table}
        WHERE aggregate_id = $1
    """
