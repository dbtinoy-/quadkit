# ruff: noqa: PT012
"""Connection reuse safety on transaction failure and cancellation."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

from quadkit.sql.exceptions import DatabaseConnectionError, TransactionError
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.fixture
async def database(tmp_path):
    driver = SQLiteProvider(str(tmp_path / "transactions.sqlite"))
    await driver.connect()
    await driver.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
    try:
        yield driver
    finally:
        connection = driver.connection_manager._connection
        if connection is not None:
            try:
                if connection.in_transaction:
                    await connection.rollback()
            except ValueError:
                pass  # Cleanup may have closed a quarantined connection.
        await driver.disconnect()


async def count(driver):
    result = await driver.execute_query("SELECT count(*) AS n FROM items")
    return result.rows[0]["n"]


@pytest.mark.asyncio
async def test_value_error_rolls_back_before_connection_is_reused(database):
    with pytest.raises(ValueError, match="application failure"):
        async with database.transaction():
            await database.execute("INSERT INTO items VALUES (1)")
            raise ValueError("application failure")
    assert await count(database) == 0
    assert not database.connection_manager._connection.in_transaction


@pytest.mark.asyncio
async def test_cancel_before_commit_waits_for_rollback_under_repeated_cancellation(
    database, monkeypatch
):
    manager = database.transaction_manager
    original_rollback = database._rollback_transaction_raw
    committing, rolling_back, release = (
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
    )

    async def delayed_commit(connection):
        committing.set()
        await asyncio.Event().wait()  # COMMIT has not been sent.

    async def delayed_rollback(connection):
        rolling_back.set()
        await release.wait()
        await original_rollback(connection)

    monkeypatch.setattr(manager, "_commit_transaction_raw", delayed_commit)
    monkeypatch.setattr(database, "_rollback_transaction_raw", delayed_rollback)

    async def write():
        async with database.transaction():
            await database.execute("INSERT INTO items VALUES (1)")

    task = asyncio.create_task(write())
    reader = None
    try:
        await asyncio.wait_for(committing.wait(), 10)
        task.cancel()
        await asyncio.wait_for(rolling_back.wait(), 10)
        task.cancel()
        reader = asyncio.create_task(count(database))
        await asyncio.sleep(0)
        assert not reader.done()  # Shared connection stays locked until cleanup.
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 10)
        assert await asyncio.wait_for(reader, 10) == 0
        assert not database.connection_manager._connection.in_transaction
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if reader is not None and not reader.done():
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancel_after_actual_commit_does_not_imply_rollback(
    database, monkeypatch
):
    manager = database.transaction_manager
    original = manager._commit_transaction_raw
    committed = asyncio.Event()

    async def lost_ack(connection):
        await original(connection)
        committed.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(manager, "_commit_transaction_raw", lost_ack)

    async def write():
        async with database.transaction():
            await database.execute("INSERT INTO items VALUES (1)")

    task = asyncio.create_task(write())
    try:
        await asyncio.wait_for(committed.wait(), 10)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await count(database) == 1
        assert not database.connection_manager._connection.in_transaction
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_failed_rollback_quarantines_manager_and_waiters(
    database, monkeypatch, capsys
):
    manager = database.transaction_manager
    rollback_started, release = asyncio.Event(), asyncio.Event()

    async def broken_rollback(connection):
        rollback_started.set()
        await release.wait()
        raise RuntimeError("sensitive rollback details")

    monkeypatch.setattr(database, "_rollback_transaction_raw", broken_rollback)

    async def write():
        async with database.transaction():
            await database.execute("INSERT INTO items VALUES (1)")
            raise ValueError("original failure")

    task = asyncio.create_task(write())
    reader = None
    try:
        await asyncio.wait_for(rollback_started.wait(), 10)
        reader = asyncio.create_task(count(database))
        await asyncio.sleep(0)
        assert not reader.done()
        release.set()
        with pytest.raises(ValueError, match="original failure"):
            await task
        with pytest.raises(
            DatabaseConnectionError, match="database connection unavailable"
        ):
            await reader
        with pytest.raises(DatabaseConnectionError):
            async with database.connection_manager.get_connection():
                pass
        with pytest.raises(DatabaseConnectionError):
            await database.connection_manager.connect()
        with pytest.raises(DatabaseConnectionError):
            await database.begin_transaction()
        with pytest.raises(DatabaseConnectionError):
            await database.commit_transaction()
        with pytest.raises(DatabaseConnectionError):
            async with manager.savepoint():
                pass
        assert not database.connection_manager.connected
        assert "sensitive rollback details" not in capsys.readouterr().out
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if reader is not None and not reader.done():
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)


@pytest.mark.asyncio
async def test_shared_pool_can_still_be_accessed_outside_quarantined_manager():
    """Document the limit: the manager cannot revoke independent raw pool users."""
    from quadkit.sql.providers.base_provider import DatabaseDriver

    connection = object()

    class Pool:
        @asynccontextmanager
        async def get_connection(self):
            yield connection

    class Driver(DatabaseDriver):
        async def _create_connection(self):
            return connection

        async def _close_connection(self, connection):
            pass

        async def _execute_query_raw(self, connection, sql, params=None):
            return []

        async def _execute_modify_raw(self, connection, sql, params=None):
            return 0

        async def _begin_transaction_raw(self, connection, isolation=None):
            pass

        async def _commit_transaction_raw(self, connection):
            pass

        async def _rollback_transaction_raw(self, connection):
            raise RuntimeError("rollback failure")

        async def _get_last_insert_id(self, connection, table):
            return None

    driver = Driver("sqlite:///:memory:")
    pool = Pool()
    driver.connection_manager.connection_pool = pool
    with pytest.raises(ValueError, match="original"):
        async with driver.transaction():
            raise ValueError("original")
    with pytest.raises(DatabaseConnectionError):
        async with driver.connection_manager.get_connection():
            pass
    async with pool.get_connection() as raw:
        assert raw is connection  # This remains a release limitation.


@pytest.mark.asyncio
async def test_failed_rollback_and_close_quarantines_without_leaking_details(
    database, monkeypatch, capsys
):
    manager = database.transaction_manager
    raw = database.connection_manager._connection

    async def broken_rollback(connection):
        raise RuntimeError("secret rollback content")

    async def broken_close(connection):
        raise RuntimeError("secret close content")

    with monkeypatch.context() as patch:
        patch.setattr(database, "_rollback_transaction_raw", broken_rollback)
        patch.setattr(database, "_close_connection", broken_close)
        with pytest.raises(ValueError, match="original"):
            async with database.transaction():
                await database.execute("INSERT INTO items VALUES (1)")
                raise ValueError("original")
        assert raw.in_transaction  # The raw connection is still unsafe.
        with pytest.raises(DatabaseConnectionError):
            async with database.connection_manager.get_connection():
                pass
        output = capsys.readouterr().out
        assert "secret rollback" not in output
        assert "secret close" not in output
    await raw.rollback()  # Test cleanup; a raw handle is outside the quarantine.


@pytest.mark.asyncio
async def test_commit_hook_failure_preserves_committed_data_and_quarantines(
    database, tmp_path, monkeypatch
):
    import sqlite3

    manager = database.transaction_manager
    rollback_calls = 0
    original_rollback = database._rollback_transaction_raw

    async def track_rollback(connection):
        nonlocal rollback_calls
        rollback_calls += 1
        await original_rollback(connection)

    async def broken_hook(*, committed):
        assert committed
        raise RuntimeError("hook failure")

    monkeypatch.setattr(database, "_rollback_transaction_raw", track_rollback)
    monkeypatch.setattr(manager, "_emit_transaction_end", broken_hook)
    with pytest.raises(RuntimeError, match="hook failure"):
        async with database.transaction():
            await database.execute("INSERT INTO items VALUES (1)")
    assert rollback_calls == 0  # COMMIT had returned, so rollback is not reported.
    with sqlite3.connect(tmp_path / "transactions.sqlite") as observer:
        assert observer.execute("SELECT count(*) FROM items").fetchone()[0] == 1
    with pytest.raises(DatabaseConnectionError):
        async with database.connection_manager.get_connection():
            pass


@pytest.mark.asyncio
async def test_rollback_hook_failure_cannot_leave_implicit_write_on_managed_connection(
    database, tmp_path, monkeypatch
):
    import sqlite3

    manager = database.transaction_manager

    async def broken_hook(*, committed):
        assert not committed
        await database.execute("INSERT INTO items VALUES (2)")
        raise RuntimeError("hook failure")

    monkeypatch.setattr(manager, "_emit_transaction_end", broken_hook)
    with pytest.raises(ValueError, match="original"):
        async with database.transaction():
            await database.execute("INSERT INTO items VALUES (1)")
            raise ValueError("original")
    with sqlite3.connect(tmp_path / "transactions.sqlite") as observer:
        assert observer.execute("SELECT count(*) FROM items").fetchone()[0] == 0
    with pytest.raises(DatabaseConnectionError):
        async with database.connection_manager.get_connection():
            pass


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_failed_rollback_and_close(
    database, monkeypatch
):
    manager = database.transaction_manager
    rollback_started = asyncio.Event()
    finish_rollback = asyncio.Event()
    close_started = asyncio.Event()
    finish_close = asyncio.Event()
    original_close = database.connection_manager._close_connection

    async def broken_rollback(_connection):
        rollback_started.set()
        await finish_rollback.wait()
        raise RuntimeError("private driver detail")

    async def slow_close(connection):
        close_started.set()
        await finish_close.wait()
        await original_close(connection)

    monkeypatch.setattr(database, "_rollback_transaction_raw", broken_rollback)
    monkeypatch.setattr(database.connection_manager, "_close_connection", slow_close)

    async def work():
        async with database.transaction():
            await database.execute("INSERT INTO items VALUES (1)")
            raise ValueError("original")

    worker = asyncio.create_task(work())
    await rollback_started.wait()
    worker.cancel()
    finish_rollback.set()
    await close_started.wait()
    worker.cancel()
    await asyncio.sleep(0)
    assert not worker.done()
    finish_close.set()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert manager.in_transaction is False
    with pytest.raises(DatabaseConnectionError):
        async with database.connection_manager.get_connection():
            pass


@pytest.mark.asyncio
async def test_raw_ambient_transaction_is_refused_without_rollback_or_commit(
    database, tmp_path
):
    import sqlite3

    connection = database.connection_manager._connection
    await connection.execute("BEGIN")
    await connection.execute("INSERT INTO items VALUES (1)")
    with pytest.raises(TransactionError, match="active transaction"):
        async with database.transaction():
            pytest.fail("managed body must not run")
    assert connection.in_transaction
    with sqlite3.connect(tmp_path / "transactions.sqlite") as observer:
        assert observer.execute("SELECT count(*) FROM items").fetchone()[0] == 0
    await connection.commit()
    async with database.transaction():
        await database.execute("INSERT INTO items VALUES (2)")
    assert await count(database) == 2


@pytest.mark.asyncio
async def test_inherited_transaction_context_is_refused_after_owner_finishes(database):
    release = asyncio.Event()

    async def child():
        await release.wait()
        with pytest.raises(TransactionError, match="belongs to another task"):
            async with database.transaction():
                pytest.fail("child cannot join the parent's finished transaction")
        with pytest.raises(TransactionError, match="belongs to another task"):
            await database.execute("INSERT INTO items VALUES (1)")

    async with database.transaction():
        task = asyncio.create_task(child())
    release.set()
    await asyncio.wait_for(task, 10)
    assert not database.connection_manager._connection.in_transaction
    assert await count(database) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "transaction",
        "savepoint",
        "query",
        "write",
        "returning",
        "get_connection",
        "begin",
        "commit",
        "rollback",
        "state",
        "connection",
        "connect",
    ],
)
async def test_child_cannot_use_inherited_context_while_parent_is_active(
    database, operation
):
    async def child():
        with pytest.raises(TransactionError, match="belongs to another task"):
            if operation == "transaction":
                async with database.transaction():
                    pytest.fail("child must not join")
            elif operation == "savepoint":
                async with database.transaction_manager.savepoint():
                    pytest.fail("child must not use parent connection")
            elif operation == "query":
                await database.execute_query("SELECT * FROM items")
            elif operation == "write":
                await database.execute("INSERT INTO items VALUES (2)")
            elif operation == "returning":
                await database.execute("INSERT INTO items VALUES (2) RETURNING id")
            elif operation == "get_connection":
                async with database.connection_manager.get_connection():
                    pytest.fail("child must not acquire")
            elif operation == "begin":
                await database.begin_transaction()
            elif operation == "commit":
                await database.commit_transaction()
            elif operation == "rollback":
                await database.rollback_transaction()
            elif operation == "state":
                _ = database.transaction_manager.in_transaction
            elif operation == "connection":
                _ = database.transaction_manager._transaction_connection
            else:
                await database.connect()

    async with database.transaction():
        await database.execute("INSERT INTO items VALUES (1)")
        await asyncio.wait_for(asyncio.create_task(child()), 3)
        assert database.transaction_manager.in_transaction
    assert await count(database) == 1


@pytest.mark.asyncio
async def test_child_with_fresh_context_can_start_independent_transaction_after_parent(
    database,
):
    import contextvars

    release = asyncio.Event()

    async def child():
        await release.wait()
        async with database.transaction():
            await database.execute("INSERT INTO items VALUES (2)")

    async with database.transaction():
        await database.execute("INSERT INTO items VALUES (1)")
        task = asyncio.create_task(child(), context=contextvars.Context())
    release.set()
    await asyncio.wait_for(task, 3)
    assert await count(database) == 2


@pytest.mark.asyncio
async def test_manual_transaction_owner_not_accessible_to_child(database):
    async def child():
        for operation in (database.commit_transaction, database.rollback_transaction):
            with pytest.raises(TransactionError, match="belongs to another task"):
                await operation()
        with pytest.raises(TransactionError, match="belongs to another task"):
            await database.execute("INSERT INTO items VALUES (2)")

    await database.begin_transaction()
    try:
        connection = database.transaction_manager._transaction_connection
        await connection.execute("INSERT INTO items VALUES (1)")
        await asyncio.wait_for(asyncio.create_task(child()), 3)
        await database.commit_transaction()
    finally:
        if database.transaction_manager.in_transaction:
            await database.rollback_transaction()
    assert await count(database) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("end", ["rollback", "cancel"])
async def test_child_inherited_from_unsuccessful_parent_is_still_refused(database, end):
    child_ready = asyncio.Event()
    release = asyncio.Event()
    child_task = None

    async def child():
        child_ready.set()
        await release.wait()
        with pytest.raises(TransactionError, match="belongs to another task"):
            await database.execute("INSERT INTO items VALUES (2)")

    async def parent():
        nonlocal child_task
        async with database.transaction():
            await database.execute("INSERT INTO items VALUES (1)")
            child_task = asyncio.create_task(child())
            await child_ready.wait()
            if end == "rollback":
                raise ValueError("roll back")
            await asyncio.Event().wait()

    parent_task = asyncio.create_task(parent())
    try:
        await asyncio.wait_for(child_ready.wait(), 3)
        if end == "cancel":
            parent_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await parent_task
        else:
            with pytest.raises(ValueError, match="roll back"):
                await parent_task
        release.set()
        assert child_task is not None
        await asyncio.wait_for(child_task, 3)
        assert await count(database) == 0
    finally:
        release.set()
        if not parent_task.done():
            parent_task.cancel()
        if child_task is not None and not child_task.done():
            child_task.cancel()
        await asyncio.gather(
            *(task for task in (parent_task, child_task) if task is not None),
            return_exceptions=True,
        )


@pytest.mark.asyncio
async def test_wait_for_creates_a_child_task_and_is_refused_before_write(database):
    async with database.transaction():
        with pytest.raises(TransactionError, match="belongs to another task"):
            await asyncio.wait_for(database.execute("INSERT INTO items VALUES (1)"), 3)
    assert await count(database) == 0
