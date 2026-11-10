"""Real SQLite transaction boundaries for the driver and its service facade."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.exceptions import TransactionError
from quadkit.sql.providers.database_service import DatabaseService
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_outer_and_nested_transactions_use_the_same_connection(pooled):
    pool = SQLiteConnectionPool(":memory:") if pooled else None
    db = SQLiteProvider(":memory:", connection_pool=pool)
    await db.connect()
    try:
        await db.execute_query("CREATE TABLE records (id TEXT PRIMARY KEY, value TEXT)")
        await db.execute_insert("records", {"id": "one", "value": "original"})
        async with db.transaction():
            await db.execute_update("records", {"value": "outer"}, '"id" = ?', ["one"])
            with pytest.raises(ValueError, match="nested"):
                async with db.transaction():
                    await db.execute_update(
                        "records", {"value": "inner"}, '"id" = ?', ["one"]
                    )
                    raise ValueError("nested")
            assert (await db.execute_query("SELECT value FROM records")).rows[0][
                "value"
            ] == "outer"
        assert (await db.execute_query("SELECT value FROM records")).rows[0][
            "value"
        ] == "outer"

        with pytest.raises(ValueError, match="outer"):
            async with db.transaction():
                await db.execute_update(
                    "records", {"value": "abort"}, '"id" = ?', ["one"]
                )
                raise ValueError("outer")
        assert (await db.execute_query("SELECT value FROM records")).rows[0][
            "value"
        ] == "outer"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_cancellation_rolls_back_and_releases_connection(pooled):
    pool = SQLiteConnectionPool(":memory:") if pooled else None
    db = SQLiteProvider(":memory:", connection_pool=pool)
    await db.connect()
    try:
        await db.execute_query("CREATE TABLE records (id TEXT PRIMARY KEY)")
        with pytest.raises(asyncio.CancelledError):
            async with db.transaction():
                await db.execute_insert("records", {"id": "one"})
                raise asyncio.CancelledError
        assert (await db.execute_query("SELECT id FROM records")).rows == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_inherited_transaction_cannot_leak_into_child_or_outlive_scope():
    db = SQLiteProvider(":memory:")
    await db.connect()
    proceed = asyncio.Event()

    async def child():
        await proceed.wait()
        await db.execute_query("SELECT 1")

    try:
        async with db.transaction():
            task = asyncio.create_task(child())
            with pytest.raises(TransactionError, match="belongs to another task"):
                await asyncio.create_task(db.execute_query("SELECT 1"))
        proceed.set()
        with pytest.raises(TransactionError, match="belongs to another task"):
            await task
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_sqlite_pool_serializes_independent_transaction_and_query():
    pool = SQLiteConnectionPool(":memory:")
    db = SQLiteProvider(":memory:", connection_pool=pool)
    await db.connect()
    started, done = asyncio.Event(), asyncio.Event()

    async def reader():
        await started.wait()
        try:
            await db.execute_query("SELECT id FROM records")
        finally:
            done.set()

    try:
        await db.execute_query("CREATE TABLE records (id TEXT PRIMARY KEY)")
        # Create outside the transaction to avoid inheriting its scope.
        task = asyncio.create_task(reader())
        async with db.transaction():
            started.set()
            await asyncio.sleep(0.02)
            assert not done.is_set()
        await asyncio.wait_for(task, timeout=1)
        assert done.is_set()
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_service_facade_pooled_nested_rollback():
    pool = SQLiteConnectionPool(":memory:")
    db = DatabaseService("sqlite:///:memory:", connection_pool=pool)
    await db.boot()
    try:
        await db.execute_query("CREATE TABLE records (id TEXT PRIMARY KEY, value TEXT)")
        await db.execute_insert("records", {"id": "one", "value": "old"})
        async with db.transaction():
            with pytest.raises(ValueError, match="nested"):
                async with db.transaction():
                    await db.execute_update(
                        "records", {"value": "new"}, '"id" = ?', ["one"]
                    )
                    raise ValueError("nested")
        result = await db.execute_query("SELECT value FROM records")
        assert result.rows[0]["value"] == "old"
    finally:
        await db.shutdown()


@pytest.mark.asyncio
async def test_failed_savepoint_rollback_marks_outer_transaction_rollback_only(
    monkeypatch,
):
    db = SQLiteProvider(":memory:")
    await db.connect()
    try:
        await db.execute_query("CREATE TABLE records (id TEXT PRIMARY KEY)")

        async def broken_rollback(*args):
            raise RuntimeError("savepoint broken")

        monkeypatch.setattr(
            db.transaction_manager, "_rollback_to_savepoint_raw", broken_rollback
        )
        with pytest.raises(RuntimeError, match="requires rollback"):
            async with db.transaction():
                try:
                    async with db.transaction():
                        await db.execute_insert("records", {"id": "one"})
                        raise ValueError("inner")
                except ValueError:
                    pass
        assert (await db.execute_query("SELECT id FROM records")).rows == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_cursor_only_driver_can_execute_savepoint_statements():
    db = SQLiteProvider(":memory:")
    calls = []

    class Cursor:
        async def execute(self, sql):
            calls.append(sql)

    class Connection:
        @asynccontextmanager
        async def cursor(self):
            yield Cursor()

    await db.transaction_manager._create_savepoint_raw(Connection(), "sp_test")
    await db.transaction_manager._release_savepoint_raw(Connection(), "sp_test")
    assert calls == ["SAVEPOINT sp_test", "RELEASE SAVEPOINT sp_test"]


@pytest.mark.asyncio
async def test_repeated_generated_savepoint_ids_do_not_alias_nested_savepoints():
    db = SQLiteProvider(":memory:")
    await db.connect()

    class RepeatedIds:
        def generate(self):
            return "12345678-abcd-1234-5678-0123456789ab"

    db.transaction_manager._id_generator = RepeatedIds()
    try:
        await db.execute_query("CREATE TABLE records (id TEXT PRIMARY KEY)")
        async with db.transaction():
            try:
                async with db.transaction():
                    await db.execute_insert("records", {"id": "outer nested"})
                    async with db.transaction():
                        await db.execute_insert("records", {"id": "inner nested"})
                    raise ValueError("undo nested")
            except ValueError:
                pass
        assert (await db.execute_query("SELECT id FROM records")).rows == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["memory", "file", "pooled"])
async def test_manual_transaction_uses_its_own_connection_for_writes(tmp_path, mode):
    path = str(tmp_path / "manual.sqlite") if mode == "file" else ":memory:"
    pool = SQLiteConnectionPool(path) if mode == "pooled" else None
    db = SQLiteProvider(path, connection_pool=pool)
    await db.connect()
    try:
        await db.execute_query("CREATE TABLE records (id TEXT PRIMARY KEY)")
        await db.begin_transaction()
        await db.execute_insert("records", {"id": "one"})
        await db.rollback_transaction()
        assert (await db.execute_query("SELECT id FROM records")).rows == []
        await db.begin_transaction()
        await db.execute_insert("records", {"id": "two"})
        await db.commit_transaction()
        assert (await db.execute_query("SELECT id FROM records")).rows[0]["id"] == "two"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_task_cancellation_rolls_back_a_pooled_transaction():
    pool = SQLiteConnectionPool(":memory:")
    db = SQLiteProvider(":memory:", connection_pool=pool)
    await db.connect()
    entered = asyncio.Event()
    try:
        await db.execute_query("CREATE TABLE records (id TEXT PRIMARY KEY)")

        async def worker():
            async with db.transaction():
                await db.execute_insert("records", {"id": "one"})
                entered.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(worker())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await db.execute_query("SELECT id FROM records")).rows == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_pooled_sqlite_service_enforces_foreign_keys():
    from quadkit.sql.exceptions import ForeignKeyError

    pool = SQLiteConnectionPool(":memory:")
    db = DatabaseService("sqlite:///:memory:", connection_pool=pool)
    await db.boot()
    try:
        await db.execute_query("CREATE TABLE parents (id TEXT PRIMARY KEY)")
        await db.execute_query(
            "CREATE TABLE children (parent_id TEXT REFERENCES parents(id))"
        )
        with pytest.raises(ForeignKeyError):
            await db.execute_insert("children", {"parent_id": "missing"})
    finally:
        await db.shutdown()
