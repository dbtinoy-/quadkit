"""Unit tests for DatabaseInboxStore — DB calls mocked at the protocol boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.data.sql.database import (
    DeleteResult,
    InsertResult,
    QueryResult,
    UpdateResult,
)
from quadkit.contracts.exceptions import DatabaseError
from quadkit.contracts.notification.inbox import InboxMessage
from quadkit.notification.inbox.database import DatabaseInboxStore


def _make_db(
    *,
    query_rows: list[dict] | None = None,
) -> MagicMock:
    """Build a minimal mock that satisfies DatabaseProviderProtocol."""
    db = MagicMock()
    db.execute = AsyncMock(return_value=None)
    db.execute_query = AsyncMock(
        return_value=QueryResult(
            rows=query_rows or [],
            row_count=len(query_rows or []),
            execution_time=0.001,
            success=True,
        )
    )
    db.execute_insert = AsyncMock(
        return_value=InsertResult(
            inserted_id="1", affected_rows=1, execution_time=0.001, success=True
        )
    )
    db.execute_update = AsyncMock(
        return_value=UpdateResult(affected_rows=1, execution_time=0.001, success=True)
    )
    db.execute_delete = AsyncMock(
        return_value=DeleteResult(affected_rows=1, execution_time=0.001, success=True)
    )
    return db


def _row(msg: InboxMessage) -> dict:
    return {
        "id": msg.id,
        "user_id": msg.user_id,
        "title": msg.title,
        "body": msg.body,
        "read": msg.read,
        "created_at": msg.created_at.isoformat(),
        "metadata": msg.metadata,
    }


class TestDatabaseInboxStore:
    """Exercises DatabaseInboxStore against a mocked DatabaseProviderProtocol."""

    @pytest.fixture
    def message(self) -> InboxMessage:
        return InboxMessage.create(user_id="u1", title="Hello", body="World")

    # ------------------------------------------------------------------
    # schema bootstrap
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_save_ensures_table_first(self, message: InboxMessage) -> None:
        """save() creates the schema via execute_query() before the insert."""
        db = _make_db()
        store = DatabaseInboxStore(db)

        await store.save(message)

        ddl_calls = [c[0][0] for c in db.execute_query.call_args_list]
        assert "CREATE TABLE IF NOT EXISTS notification_inbox_messages" in ddl_calls[0]
        assert "CREATE INDEX IF NOT EXISTS" in ddl_calls[1]
        db.execute_insert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_read_ops_ensure_table(self, message: InboxMessage) -> None:
        """get()/list_for_user()/count_unread() bootstrap the schema too."""
        db = _make_db(query_rows=[_row(message)])
        store = DatabaseInboxStore(db)

        await store.get(message.id)
        await store.list_for_user(message.user_id)
        await store.count_unread(message.user_id)

        ddl_calls = [c[0][0] for c in db.execute_query.call_args_list]
        assert any(
            "CREATE TABLE IF NOT EXISTS notification_inbox_messages" in s
            for s in ddl_calls
        )
        assert any(
            "CREATE INDEX IF NOT EXISTS notification_inbox_messages_user_created_idx"
            in s
            for s in ddl_calls
        )

    @pytest.mark.asyncio
    async def test_schema_ensure_uses_custom_table(self, message: InboxMessage) -> None:
        """The ensure step targets the configured table name."""
        db = _make_db()
        store = DatabaseInboxStore(db, table="custom_inbox")

        await store.save(message)

        assert "CREATE TABLE IF NOT EXISTS custom_inbox" in str(
            db.execute_query.call_args_list[0][0][0]
        )
        assert db.execute_insert.call_args[0][0] == "custom_inbox"

    # ------------------------------------------------------------------
    # save
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_save_calls_execute_insert(self, message: InboxMessage) -> None:
        """save() calls execute_insert with all message fields."""
        db = _make_db()
        store = DatabaseInboxStore(db)
        await store.save(message)

        db.execute_insert.assert_awaited_once()
        call_args = db.execute_insert.call_args
        table, data = call_args[0]
        assert table == "notification_inbox_messages"
        assert data["id"] == message.id
        assert data["user_id"] == message.user_id
        assert data["title"] == message.title
        assert data["body"] == message.body

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_returns_message_when_found(self, message: InboxMessage) -> None:
        """get() returns an InboxMessage when the DB returns one row."""
        db = _make_db(query_rows=[_row(message)])
        store = DatabaseInboxStore(db)

        result = await store.get(message.id)
        assert result is not None
        assert result.id == message.id
        assert result.title == "Hello"
        assert result.read is False

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self) -> None:
        """get() returns None when the DB returns no rows."""
        db = _make_db(query_rows=[])
        store = DatabaseInboxStore(db)

        result = await store.get("missing-id")
        assert result is None

    # ------------------------------------------------------------------
    # list_for_user
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_for_user_all(self, message: InboxMessage) -> None:
        """list_for_user() calls execute_query without unread filter."""
        db = _make_db(query_rows=[_row(message)])
        store = DatabaseInboxStore(db)

        results = await store.list_for_user("u1")
        assert len(results) == 1
        assert results[0].id == message.id

        sql_arg = db.execute_query.call_args[0][0]
        assert "AND read = FALSE" not in sql_arg

    @pytest.mark.asyncio
    async def test_list_for_user_unread_only_adds_filter(
        self, message: InboxMessage
    ) -> None:
        """list_for_user(unread_only=True) includes the unread filter in SQL."""
        db = _make_db(query_rows=[_row(message)])
        store = DatabaseInboxStore(db)

        await store.list_for_user("u1", unread_only=True)

        sql_arg = db.execute_query.call_args[0][0]
        assert "AND read = FALSE" in sql_arg

    # ------------------------------------------------------------------
    # mark_read
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_mark_read_calls_execute_update(self, message: InboxMessage) -> None:
        """mark_read() calls execute_update with read=True."""
        db = _make_db()
        store = DatabaseInboxStore(db)
        await store.mark_read(message.id, message.user_id)

        db.execute_update.assert_awaited_once()
        call_args = db.execute_update.call_args[0]
        assert call_args[1] == {"read": True}

    # ------------------------------------------------------------------
    # mark_all_read
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_mark_all_read_calls_execute_update(self) -> None:
        """mark_all_read() calls execute_update with unread filter."""
        db = _make_db()
        store = DatabaseInboxStore(db)
        await store.mark_all_read("u1")

        db.execute_update.assert_awaited_once()
        call_args = db.execute_update.call_args[0]
        assert call_args[1] == {"read": True}
        assert "read = FALSE" in call_args[2]

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_calls_execute_delete(self, message: InboxMessage) -> None:
        """delete() calls execute_delete with correct where clause."""
        db = _make_db()
        store = DatabaseInboxStore(db)
        await store.delete(message.id, message.user_id)

        db.execute_delete.assert_awaited_once()

    # ------------------------------------------------------------------
    # count_unread
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_count_unread_returns_count_from_db(self) -> None:
        """count_unread() extracts the cnt column from the query result."""
        db = _make_db(query_rows=[{"cnt": 7}])
        store = DatabaseInboxStore(db)

        count = await store.count_unread("u1")
        assert count == 7

    @pytest.mark.asyncio
    async def test_count_unread_returns_zero_on_empty_rows(self) -> None:
        """count_unread() returns 0 when DB returns no rows."""
        db = _make_db(query_rows=[])
        store = DatabaseInboxStore(db)

        count = await store.count_unread("u1")
        assert count == 0

    # ------------------------------------------------------------------
    # _row_to_message
    # ------------------------------------------------------------------

    def test_row_to_message_parses_iso_datetime(self) -> None:
        """_row_to_message() parses ISO-format datetime strings."""
        ts = datetime.now(UTC)
        row = {
            "id": "msg-1",
            "user_id": "u1",
            "title": "T",
            "body": "B",
            "read": False,
            "created_at": ts.isoformat(),
            "metadata": {},
        }
        msg = DatabaseInboxStore._row_to_message(row)
        assert msg.id == "msg-1"
        assert msg.created_at == ts

    def test_row_to_message_falls_back_for_non_datetime(self) -> None:
        """_row_to_message() substitutes now(UTC) for unrecognised datetime types."""
        row = {
            "id": "msg-2",
            "user_id": "u2",
            "title": "T",
            "body": "B",
            "read": True,
            "created_at": 9999,  # unexpected type
            "metadata": None,
        }
        msg = DatabaseInboxStore._row_to_message(row)
        assert msg.read is True
        assert msg.metadata == {}

    def test_row_to_message_accepts_real_datetime(self) -> None:
        """_row_to_message() accepts an already-parsed datetime object."""
        ts = datetime.now(UTC)
        row = {
            "id": "msg-3",
            "user_id": "u3",
            "title": "T",
            "body": "B",
            "read": False,
            "created_at": ts,
            "metadata": {"key": "val"},
        }
        msg = DatabaseInboxStore._row_to_message(row)
        assert msg.created_at == ts
        assert msg.metadata == {"key": "val"}

    # ------------------------------------------------------------------
    # custom table name
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_custom_table_name_is_used_in_queries(self) -> None:
        """Custom table name flows through to all SQL statements."""
        db = _make_db(query_rows=[])
        store = DatabaseInboxStore(db, table="my_inbox")
        await store.list_for_user("u1")

        sql = db.execute_query.call_args[0][0]
        assert "my_inbox" in sql

    # ------------------------------------------------------------------
    # health_check
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check_uses_query_signature_without_extra_kwargs(self) -> None:
        """health_check() uses the standard execute_query(sql, params) signature."""

        async def strict_execute_query(
            sql: str, params: list[object] | None = None
        ) -> QueryResult:
            return QueryResult(
                rows=[],
                row_count=0,
                execution_time=0.001,
                success=True,
            )

        db = _make_db(query_rows=[])
        db.execute_query = AsyncMock(side_effect=strict_execute_query)
        store = DatabaseInboxStore(db, table="custom_inbox")

        result = await store.health_check(timeout=2.5)

        assert result.component == "inbox_store"
        assert result.status == HealthStatus.HEALTHY
        assert result.details == {"backend": "database", "table": "custom_inbox"}
        db.execute_query.assert_awaited_once_with(
            "SELECT 1 FROM custom_inbox LIMIT 1",
            [],
        )

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_when_probe_fails(self) -> None:
        """health_check() returns unhealthy when the probe raises."""
        db = _make_db(query_rows=[])
        db.execute_query.side_effect = RuntimeError("table missing")
        store = DatabaseInboxStore(db)

        result = await store.health_check()

        assert result.component == "inbox_store"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "table missing"

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_for_database_error(self) -> None:
        """health_check() converts Quadkit DB errors into unhealthy results."""
        db = _make_db(query_rows=[])
        db.execute_query.side_effect = DatabaseError("db unavailable")
        store = DatabaseInboxStore(db)

        result = await store.health_check()

        assert result.component == "inbox_store"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.error is not None
        assert "db unavailable" in result.error


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-11-03 12:00:00.123456",
        "2026-11-03T12:00:00.123456+00:00",
        "2026-11-03T14:00:00.123456+02:00",
        datetime(2026, 11, 3, 12, 0, 0, 123456),
        datetime.fromisoformat("2026-11-03T07:00:00.123456-05:00"),
    ],
)
def test_inbox_hydration_restores_canonical_utc(timestamp):
    """Native naive-UTC bindings and offset-aware drivers have one public shape."""
    row = {
        "id": "one",
        "user_id": "recipient",
        "title": "Published",
        "body": "Body",
        "created_at": timestamp,
    }
    message = DatabaseInboxStore._row_to_message(row)
    assert message.created_at == datetime(2026, 11, 3, 12, 0, 0, 123456, tzinfo=UTC)
    assert message.created_at.tzinfo is UTC
