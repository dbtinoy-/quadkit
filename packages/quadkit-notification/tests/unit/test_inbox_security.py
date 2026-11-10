"""Inbox boundaries exercised against the local framework's SQLite driver."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.data.sql.database import (
    DeleteResult,
    InsertResult,
    QueryResult,
    UpdateResult,
)
from quadkit.contracts.notification.inbox import InboxMessage
from quadkit.notification.inbox.database import DatabaseInboxStore
from quadkit.notification.inbox.service import InboxService


@pytest.mark.asyncio
async def test_sqlite_inbox_owner_reads_and_writes_survive_restart(
    tmp_path: Path,
) -> None:
    SQLiteProvider = pytest.importorskip(
        "quadkit.sql.providers.sqlite_provider"
    ).SQLiteProvider
    db_path = str(tmp_path / "inbox.sqlite")
    provider = SQLiteProvider(db_path)
    await provider.connect()
    try:
        service = InboxService(DatabaseInboxStore(provider))
        alice = await service.send("alice", "Private", "Body", order="one")
        bob = await service.send("bob", "Other", "Body")
        assert (await service.get_message_for_user(alice.id, "alice")) == alice
        assert await service.get_message_for_user(alice.id, "bob") is None
        assert await service.get_message_for_user("missing", "bob") is None
        with pytest.raises(ValueError, match="authenticated user ID"):
            await service.get_message_for_user(alice.id, "")
        assert [m.id for m in await service.get_inbox("bob")] == [bob.id]
        await service.mark_read(alice.id, "bob")
        await service.delete(alice.id, "bob")
        assert (await service.get_message_for_user(alice.id, "alice")) == alice
        await service.mark_read(alice.id, "alice")
        assert (await service.get_message_for_user(alice.id, "alice")).read is True
    finally:
        await provider.disconnect()

    restarted = SQLiteProvider(db_path)
    await restarted.connect()
    try:
        service = InboxService(DatabaseInboxStore(restarted))
        message = await service.get_message_for_user(alice.id, "alice")
        assert message is not None
        assert message.read
        assert message.metadata == {"order": "one"}
        assert await service.get_message_for_user(alice.id, "bob") is None
        await service.delete(alice.id, "alice")
        assert await service.get_message_for_user(alice.id, "alice") is None
        assert await service.get_message_for_user(bob.id, "bob") is not None
    finally:
        await restarted.disconnect()


@pytest.mark.parametrize(
    "table", ["bad-name", "inbox;DROP TABLE users", "a.b", "", "1start"]
)
def test_invalid_table_identifier_is_rejected(table: str) -> None:
    with pytest.raises(ValueError, match="plain SQL identifier"):
        DatabaseInboxStore(MagicMock(), table=table)


def _provider() -> MagicMock:
    db = MagicMock()
    db.execute_query = AsyncMock(
        return_value=QueryResult(rows=[], row_count=0, execution_time=0.0, success=True)
    )
    db.execute_insert = AsyncMock(
        return_value=InsertResult(
            inserted_id="1", affected_rows=1, execution_time=0.0, success=True
        )
    )
    db.execute_update = AsyncMock(
        return_value=UpdateResult(affected_rows=1, execution_time=0.0, success=True)
    )
    db.execute_delete = AsyncMock(
        return_value=DeleteResult(affected_rows=1, execution_time=0.0, success=True)
    )
    return db


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "schema",
        "save",
        "get",
        "get_for_user",
        "list",
        "list_page",
        "mark_read",
        "mark_all_read",
        "delete",
        "count",
        "clear",
    ],
)
async def test_reported_database_failure_never_looks_successful(operation: str) -> None:
    db = _provider()
    store = DatabaseInboxStore(db)
    query_fail = QueryResult(rows=[], row_count=0, execution_time=0.0, success=False)
    if operation == "schema":
        db.execute_query.return_value = query_fail
    elif operation in {"get", "get_for_user", "list", "list_page", "count", "clear"}:
        db.execute_query.side_effect = [
            db.execute_query.return_value,
            db.execute_query.return_value,
            query_fail,
        ]
    elif operation == "save":
        db.execute_insert.return_value = InsertResult(
            inserted_id=None, affected_rows=0, execution_time=0.0, success=False
        )
    elif operation in {"mark_read", "mark_all_read"}:
        db.execute_update.return_value = UpdateResult(
            affected_rows=0, execution_time=0.0, success=False
        )
    else:
        db.execute_delete.return_value = DeleteResult(
            affected_rows=0, execution_time=0.0, success=False
        )

    calls = {
        "schema": lambda: store.get("id"),
        "save": lambda: store.save(InboxMessage.create("alice", "title", "body")),
        "get": lambda: store.get("id"),
        "get_for_user": lambda: store.get_for_user("id", "alice"),
        "list": lambda: store.list_for_user("alice"),
        "list_page": lambda: store.list_page_for_user("alice", limit=10, offset=0),
        "mark_read": lambda: store.mark_read("id", "alice"),
        "mark_all_read": lambda: store.mark_all_read("alice"),
        "delete": lambda: store.delete("id", "alice"),
        "count": lambda: store.count_unread("alice"),
        "clear": lambda: store.clear_all("alice"),
    }
    with pytest.raises(RuntimeError, match="inbox database operation failed"):
        await calls[operation]()


@pytest.mark.asyncio
async def test_bounded_owner_queries_use_parameters_and_fail_closed() -> None:
    db = _provider()
    store = DatabaseInboxStore(db)
    assert await store.get_for_user("message", "alice") is None
    sql, params = db.execute_query.await_args.args
    assert "WHERE id = ? AND user_id = ?" in sql
    assert params == ["message", "alice"]

    assert (
        await store.list_page_for_user("alice", unread_only=True, limit=2, offset=3)
        == []
    )
    sql, params = db.execute_query.await_args.args
    assert "WHERE user_id = ? AND read = FALSE" in sql
    assert "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?" in sql
    assert params == ["alice", 2, 3]
    failed = QueryResult(rows=[], row_count=0, execution_time=0.0, success=False)
    db.execute_query.side_effect = [db.execute_query.return_value] * 2 + [failed]
    with pytest.raises(RuntimeError, match="inbox database operation failed"):
        await store.list_page_for_user("alice", limit=2, offset=0)


@pytest.mark.asyncio
async def test_scoped_lookup_still_checks_the_store_response() -> None:
    message = InboxMessage.create("alice", "private", "body")
    store = MagicMock()
    store.get_for_user = AsyncMock(return_value=message)
    store.get = AsyncMock()
    service = InboxService(store)
    assert await service.get_message_for_user(message.id, "bob") is None
    store.get_for_user.assert_awaited_once_with(message.id, "bob")
    store.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_store_still_supports_scoped_lookup_and_paging() -> None:
    from quadkit.contracts.notification.inbox import InboxStoreProtocol

    messages = [InboxMessage.create("alice", str(i), "body") for i in range(3)]
    store = MagicMock(spec=InboxStoreProtocol)
    store.get = AsyncMock(return_value=messages[0])
    store.list_for_user = AsyncMock(return_value=messages)
    service = InboxService(store)
    assert await service.get_message_for_user(messages[0].id, "bob") is None
    assert await service.get_message_for_user(messages[0].id, "alice") == messages[0]
    assert await service.get_inbox("alice", limit=1, offset=1) == messages[1:2]
    store.list_for_user.assert_awaited_once_with("alice", unread_only=False)


@pytest.mark.asyncio
async def test_explicit_falsey_store_is_never_replaced_with_memory() -> None:
    from quadkit.notification.inbox.memory import InMemoryInboxStore

    class FalseyStore(InMemoryInboxStore):
        def __bool__(self) -> bool:
            return False

    store = FalseyStore()
    service = InboxService(store)
    message = await service.send("alice", "title", "body")
    assert await store.get(message.id) == message


@pytest.mark.asyncio
@pytest.mark.parametrize("paged", [False, True])
async def test_mismatched_list_owner_fails_before_read_side_effects(
    paged: bool,
) -> None:
    from quadkit.contracts.notification.inbox import InboxStoreProtocol
    from quadkit.notification.config import InboxConfig

    alice = InboxMessage.create("alice", "private", "body")
    bob = InboxMessage.create("bob", "other", "body")
    store = MagicMock(spec=InboxStoreProtocol)
    store.mark_read = AsyncMock()
    store.list_for_user = AsyncMock(return_value=[bob, alice])
    if paged:
        store.list_page_for_user = AsyncMock(return_value=[bob, alice])
    service = InboxService(store, config=InboxConfig(mark_read_on_fetch=True))
    with pytest.raises(
        RuntimeError, match="inbox store returned a message for another user"
    ):
        await service.get_inbox("bob", limit=1)
    store.mark_read.assert_not_awaited()


@pytest.mark.asyncio
async def test_paged_store_must_honor_requested_page_ceiling() -> None:
    store = MagicMock()
    store.list_page_for_user = AsyncMock(
        return_value=[InboxMessage.create("alice", str(i), "body") for i in range(2)]
    )
    service = InboxService(store)
    with pytest.raises(
        RuntimeError, match="inbox store exceeded the requested page size"
    ):
        await service.get_inbox("alice", limit=1)


@pytest.mark.asyncio
async def test_count_rejects_mis_scoped_legacy_store_list() -> None:
    store = MagicMock()
    store.list_for_user = AsyncMock(
        return_value=[InboxMessage.create("alice", "private", "body")]
    )
    service = InboxService(store)
    with pytest.raises(
        RuntimeError, match="inbox store returned a message for another user"
    ):
        await service.count("bob")


@pytest.mark.asyncio
@pytest.mark.parametrize("scoped", [False, True])
async def test_single_lookup_rejects_the_wrong_message_id(scoped: bool) -> None:
    from quadkit.contracts.notification.inbox import InboxStoreProtocol

    store = MagicMock(spec=InboxStoreProtocol)
    wrong = InboxMessage.create("alice", "private", "body")
    store.get = AsyncMock(return_value=wrong)
    if scoped:
        store.get_for_user = AsyncMock(return_value=wrong)
    assert (
        await InboxService(store).get_message_for_user("different-id", "alice") is None
    )
