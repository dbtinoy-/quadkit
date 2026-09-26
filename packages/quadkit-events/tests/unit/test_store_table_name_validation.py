"""Table-name validation at events SQL store construction time."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.events.stores.checkpoints import SqlCheckpointStore
from quadkit.events.stores.idempotency import SqlIdempotencyStore

TENANT_PREFIXED = "tenant_42_events"


class TestSqlIdempotencyStoreTableName:
    """SqlIdempotencyStore validates table_name in __init__."""

    def test_default_table_name_accepted(self) -> None:
        store = SqlIdempotencyStore(connection=MagicMock())
        assert store.table_name == "event_idempotency"

    def test_valid_custom_table_name_accepted(self) -> None:
        store = SqlIdempotencyStore(connection=MagicMock(), table_name=TENANT_PREFIXED)
        assert store.table_name == TENANT_PREFIXED

    def test_max_length_table_name_accepted(self) -> None:
        store = SqlIdempotencyStore(connection=MagicMock(), table_name="e" * 63)
        assert store.table_name == "e" * 63

    def test_sql_metacharacter_table_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            SqlIdempotencyStore(
                connection=MagicMock(), table_name="events; DROP TABLE events"
            )

    def test_quoted_table_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            SqlIdempotencyStore(connection=MagicMock(), table_name='events"')


class TestSqlCheckpointStoreTableName:
    """SqlCheckpointStore validates table_name (and its _locks suffix)."""

    def test_default_table_name_accepted(self) -> None:
        store = SqlCheckpointStore(connection=MagicMock())
        assert store.table_name == "event_checkpoints"

    def test_valid_custom_table_name_accepted(self) -> None:
        store = SqlCheckpointStore(connection=MagicMock(), table_name=TENANT_PREFIXED)
        assert store.table_name == TENANT_PREFIXED

    def test_sql_metacharacter_table_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            SqlCheckpointStore(
                connection=MagicMock(), table_name="events; DROP TABLE events"
            )

    def test_table_name_must_leave_room_for_locks_suffix(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            SqlCheckpointStore(connection=MagicMock(), table_name="e" * 60)
        store = SqlCheckpointStore(connection=MagicMock(), table_name="e" * 57)
        assert store.table_name == "e" * 57
