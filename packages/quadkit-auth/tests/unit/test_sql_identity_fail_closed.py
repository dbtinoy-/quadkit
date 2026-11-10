"""SQL identity storage must not turn reported database failures into success."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from quadkit.auth.models.user import User, UserCredentials
from quadkit.auth.storage._sql_store import SQLUserStore
from quadkit.contracts.data.sql.database import (
    DeleteResult,
    InsertResult,
    QueryResult,
    UpdateResult,
)
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


def failed_query(rows=None):
    return QueryResult(
        rows=rows or [],
        row_count=0,
        execution_time=0,
        success=False,
        error_message="database error",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_statement", [0, 1, 2])
async def test_failed_schema_statements_never_mark_initialized(failed_statement):
    results = [
        QueryResult(rows=[], row_count=0, execution_time=0, success=True)
        for _ in range(3)
    ]
    results[failed_statement] = failed_query()
    db = SimpleNamespace(execute=AsyncMock(side_effect=results))
    store = SQLUserStore(db)
    with pytest.raises(RuntimeError, match="identity store database"):
        await store.initialize()
    assert not store.initialized
    assert db.execute.await_count == failed_statement + 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "get_user_by_id",
        "get_user_by_email",
        "get_credentials",
        "list_users",
        "count_users",
        "create_user",
    ],
)
async def test_reported_read_failure_is_not_success_or_not_found(method):
    db = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=failed_query(
                [
                    {
                        "user_id": "u",
                        "name": "A",
                        "email": "a@example.test",
                        "is_active": True,
                    }
                ]
            )
        ),
        execute_insert=AsyncMock(),
    )
    store = SQLUserStore(db)
    store._initialized = True
    args = {
        "get_user_by_id": ("u",),
        "get_user_by_email": ("a@example.test",),
        "get_credentials": ("u",),
        "list_users": (),
        "count_users": (),
        "create_user": ("A", "a@example.test", None),
    }[method]
    with pytest.raises(RuntimeError, match="identity store database"):
        await getattr(store, method)(*args)
    db.execute_insert.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method", ["create_user", "update_user", "delete_user", "update_credentials"]
)
async def test_reported_write_failure_never_reports_success(method):
    db = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=QueryResult(
                rows=[], row_count=0, execution_time=0, success=True
            )
        ),
        execute_insert=AsyncMock(
            return_value=InsertResult(
                inserted_id=None,
                affected_rows=0,
                execution_time=0,
                success=False,
                error_message="database error",
            )
        ),
        execute_update=AsyncMock(
            return_value=UpdateResult(
                affected_rows=0,
                execution_time=0,
                success=False,
                error_message="database error",
            )
        ),
        execute_delete=AsyncMock(
            return_value=DeleteResult(
                affected_rows=0,
                execution_time=0,
                success=False,
                error_message="database error",
            )
        ),
    )
    store = SQLUserStore(db)
    store._initialized = True
    user = User(user_id="u", name="A", email="a@example.test")
    args = {
        "create_user": ("A", "a@example.test", None),
        "update_user": (user,),
        "delete_user": ("u",),
        "update_credentials": (UserCredentials(user_id="u", hashed_password="hash"),),
    }[method]
    with pytest.raises(RuntimeError, match="identity store database"):
        await getattr(store, method)(*args)


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", ["false", 2, -1])
async def test_malformed_sql_active_flags_do_not_activate_user(stored):
    db = SQLiteProvider(":memory:")
    await db.connect()
    try:
        store = SQLUserStore(db)
        user = await store.create_user("A", "a@example.test", None)
        # SQLite's dynamic typing allows these values despite BOOLEAN affinity.
        await db.execute(
            "UPDATE users SET is_active = ? WHERE user_id = ?", [stored, user.user_id]
        )
        result = await store.get_user_by_id(user.user_id)
        assert result is not None
        assert result.is_active is False
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_absent_active_column_does_not_activate_user():
    store = SQLUserStore(object())
    user = await store._user_from_row(
        {"user_id": "u", "name": "A", "email": "a@example.test"}
    )
    assert not user.is_active


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", ["false", "0", "1", 2, -1, None])
async def test_unrecognized_active_representations_are_inactive(stored):
    store = SQLUserStore(object())
    user = await store._user_from_row(
        {"user_id": "u", "name": "A", "email": "a@example.test", "is_active": stored}
    )
    assert not user.is_active


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", [True, 1])
async def test_canonical_active_representations_are_active(stored):
    store = SQLUserStore(object())
    user = await store._user_from_row(
        {"user_id": "u", "name": "A", "email": "a@example.test", "is_active": stored}
    )
    assert user.is_active


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", ["false", "0", "1", 2, -1, None])
async def test_unrecognized_verified_representations_are_not_verified(stored):
    store = SQLUserStore(object())
    user = await store._user_from_row(
        {
            "user_id": "u",
            "name": "A",
            "email": "a@example.test",
            "is_active": 1,
            "is_verified": stored,
        }
    )
    assert not user.is_verified


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", [True, 1])
async def test_canonical_verified_representations_are_verified(stored):
    store = SQLUserStore(object())
    user = await store._user_from_row(
        {
            "user_id": "u",
            "name": "A",
            "email": "a@example.test",
            "is_active": 1,
            "is_verified": stored,
        }
    )
    assert user.is_verified


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_success", [None, 0, 1, "true"])
async def test_canonical_result_requires_explicit_boolean_success(bad_success):
    result = QueryResult(rows=[], row_count=0, execution_time=0, success=bad_success)
    store = SQLUserStore(SimpleNamespace(execute=AsyncMock(return_value=result)))
    with pytest.raises(RuntimeError, match="identity store database"):
        await store.initialize()
    assert not store.initialized


@pytest.mark.asyncio
async def test_failed_schema_initialization_can_retry_on_real_sqlite():
    db = SQLiteProvider(":memory:")
    await db.connect()
    try:

        class FailsOnce:
            def __init__(self):
                self.calls = 0

            async def execute(self, statement):
                self.calls += 1
                if self.calls == 2:
                    return failed_query()
                return await db.execute(statement)

        proxy = FailsOnce()
        store = SQLUserStore(proxy)
        with pytest.raises(RuntimeError, match="identity store database") as exc:
            await store.initialize()
        assert "database error" not in str(exc.value)
        assert not store.initialized
        await store.initialize()
        assert store.initialized
        assert await db.table_exists("users")
        indexes = await db.execute_query("PRAGMA index_list(users)")
        names = {row["name"] for row in indexes.rows}
        assert {"idx_users_email", "idx_users_name"} <= names
    finally:
        await db.disconnect()
