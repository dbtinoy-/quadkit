# ruff: noqa: PT012
"""Managed SQL operations must use the physical transaction connection."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import aiosqlite
import pytest

from quadkit.sql.exceptions import DatabaseConnectionError, TransactionError
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


class DeliberateRollbackError(Exception):
    """Sentinel used to distinguish a planned rollback from driver errors."""


class SQLitePool:
    def __init__(self, path, size=2):
        self.path = path
        self.size = size
        self.queue = asyncio.Queue()
        self.connections = []
        self.acquisitions = 0

    async def initialize(self):
        if self.connections:
            return
        for _ in range(self.size):
            conn = await aiosqlite.connect(self.path)
            conn.row_factory = aiosqlite.Row
            self.connections.append(conn)
            self.queue.put_nowait(conn)

    @asynccontextmanager
    async def get_connection(self):
        conn = await self.queue.get()
        self.acquisitions += 1
        try:
            yield conn
        finally:
            self.queue.put_nowait(conn)

    async def shutdown(self):
        for conn in self.connections:
            await conn.close()


@pytest.mark.asyncio
async def test_pooled_sqlite_queries_bind_to_the_transaction_connection(tmp_path):
    path = tmp_path / "pool.sqlite"
    pool = SQLitePool(path)
    driver = SQLiteProvider(str(path), connection_pool=pool)
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")
    try:
        async with driver.transaction():
            owner = driver.transaction_manager._transaction_connection
            async with driver.connection_manager.get_connection() as borrowed:
                assert borrowed is owner
            await driver.execute("INSERT INTO items VALUES(1)")
            result = await driver.execute_query("SELECT id FROM items")
            assert result.rows == [{"id": 1}]
        async with aiosqlite.connect(path) as observer:
            async with observer.execute("SELECT id FROM items") as cursor:
                assert await cursor.fetchall() == [(1,)]
    finally:
        for conn in pool.connections:
            if conn.in_transaction:
                await conn.rollback()
        await driver.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("commit", [False, True])
async def test_pooled_sqlite_commit_and_rollback_use_one_lease(tmp_path, commit):
    path = tmp_path / "pool-outcome.sqlite"
    pool = SQLitePool(path)
    driver = SQLiteProvider(str(path), connection_pool=pool)
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")
    try:
        try:
            async with driver.transaction():
                acquired = pool.acquisitions
                assert pool.queue.qsize() == 1
                await driver.execute("INSERT INTO items VALUES(1)")
                assert (await driver.execute_query("SELECT id FROM items")).rows == [
                    {"id": 1}
                ]
                assert pool.acquisitions == acquired
                if not commit:
                    raise DeliberateRollbackError
        except DeliberateRollbackError:
            assert not commit
        assert pool.queue.qsize() == 2
        assert all(not conn.in_transaction for conn in pool.connections)
        async with aiosqlite.connect(path) as observer:
            async with observer.execute("SELECT id FROM items") as cursor:
                assert await cursor.fetchall() == ([(1,)] if commit else [])
    finally:
        await driver.disconnect()


@pytest.mark.asyncio
async def test_pooled_savepoint_operates_on_bound_connection(tmp_path):
    path = tmp_path / "pool-savepoint.sqlite"
    pool = SQLitePool(path)
    driver = SQLiteProvider(str(path), connection_pool=pool)
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")
    try:
        async with driver.transaction():
            await driver.execute("INSERT INTO items VALUES(1)")
            with pytest.raises(ValueError, match="inner"):
                async with driver.transaction_manager.savepoint():
                    await driver.execute("INSERT INTO items VALUES(2)")
                    raise ValueError("inner")
        async with aiosqlite.connect(path) as observer:
            async with observer.execute("SELECT id FROM items") as cursor:
                assert await cursor.fetchall() == [(1,)]
    finally:
        await driver.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("commit", [False, True])
async def test_manual_sqlite_transaction_queries_use_manual_connection(
    tmp_path, commit
):
    path = tmp_path / "manual.sqlite"
    driver = SQLiteProvider(str(path))
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")
    try:
        await driver.begin_transaction()
        owner = driver.transaction_manager._transaction_connection
        async with driver.connection_manager.get_connection() as borrowed:
            assert borrowed is owner
        await driver.execute("INSERT INTO items VALUES(1)")
        assert (await driver.execute_query("SELECT id FROM items")).rows == [{"id": 1}]
        if commit:
            await driver.commit_transaction()
        else:
            await driver.rollback_transaction()
        async with aiosqlite.connect(path) as observer:
            async with observer.execute("SELECT id FROM items") as cursor:
                assert await cursor.fetchall() == ([(1,)] if commit else [])
    finally:
        if driver.transaction_manager.in_transaction:
            await driver.rollback_transaction()
        await driver.disconnect()


@pytest.mark.asyncio
async def test_cancelled_pooled_transaction_rolls_back_before_pool_return(
    tmp_path, monkeypatch
):
    path = tmp_path / "pool-cancel.sqlite"
    pool = SQLitePool(path)
    driver = SQLiteProvider(str(path), connection_pool=pool)
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")
    at_commit = asyncio.Event()

    async def blocked_commit(connection):
        at_commit.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        driver.transaction_manager, "_commit_transaction_raw", blocked_commit
    )

    async def write():
        async with driver.transaction():
            await driver.execute("INSERT INTO items VALUES(1)")

    task = asyncio.create_task(write())
    try:
        await asyncio.wait_for(at_commit.wait(), 3)
        assert pool.queue.qsize() == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert pool.queue.qsize() == 2
        assert all(not conn.in_transaction for conn in pool.connections)
        async with aiosqlite.connect(path) as observer:
            async with observer.execute("SELECT id FROM items") as cursor:
                assert await cursor.fetchall() == []
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await driver.disconnect()


@pytest.mark.asyncio
async def test_generated_savepoint_identifier_may_start_with_digit(tmp_path):
    from types import SimpleNamespace

    driver = SQLiteProvider(str(tmp_path / "savepoint.sqlite"))
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")
    driver.transaction_manager._id_generator = SimpleNamespace(
        generate=lambda: "123456789abc"
    )
    try:
        async with driver.transaction():
            async with driver.transaction_manager.savepoint():
                await driver.execute("INSERT INTO items VALUES(1)")
        assert (await driver.execute_query("SELECT id FROM items")).rows == [{"id": 1}]
    finally:
        await driver.disconnect()


@pytest.mark.asyncio
async def test_single_connection_pool_does_not_deadlock_on_nested_query(tmp_path):
    pool = SQLitePool(tmp_path / "one.sqlite", size=1)
    driver = SQLiteProvider(str(pool.path), connection_pool=pool)
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")

    async def work():
        async with driver.transaction():
            await driver.execute("INSERT INTO items VALUES(1)")
            assert (await driver.execute_query("SELECT id FROM items")).rows == [
                {"id": 1}
            ]

    try:
        await asyncio.wait_for(work(), 3)
    finally:
        await driver.disconnect()


@pytest.mark.asyncio
async def test_successful_commit_hook_with_implicit_write_quarantines_connection(
    tmp_path, monkeypatch
):
    """Do not return a known connection with hook-created pending work as usable."""
    pool = SQLitePool(tmp_path / "hook.sqlite")
    driver = SQLiteProvider(str(pool.path), connection_pool=pool)
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")

    async def hook(*, committed):
        assert committed
        await driver.execute("INSERT INTO items VALUES(2)")

    monkeypatch.setattr(driver.transaction_manager, "_emit_transaction_end", hook)
    try:
        with pytest.raises(TransactionError, match="active transaction"):
            async with driver.transaction():
                await driver.execute("INSERT INTO items VALUES(1)")
        assert not driver.connection_manager.connected
        with pytest.raises(DatabaseConnectionError):
            async with driver.connection_manager.get_connection():
                pass
        async with aiosqlite.connect(pool.path) as observer:
            async with observer.execute("SELECT id FROM items ORDER BY id") as cursor:
                assert await cursor.fetchall() == [(1,)]  # COMMIT had succeeded.
    finally:
        await driver.disconnect()


@pytest.mark.asyncio
async def test_successful_read_only_commit_hook_keeps_connection_usable(
    tmp_path, monkeypatch
):
    pool = SQLitePool(tmp_path / "hook-read.sqlite", size=1)
    driver = SQLiteProvider(str(pool.path), connection_pool=pool)
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")

    async def hook(*, committed):
        assert committed
        assert (await driver.execute_query("SELECT id FROM items")).rows == [{"id": 1}]

    monkeypatch.setattr(driver.transaction_manager, "_emit_transaction_end", hook)
    try:
        async with driver.transaction():
            await driver.execute("INSERT INTO items VALUES(1)")
        assert driver.connection_manager.connected
        assert (await driver.execute_query("SELECT id FROM items")).rows == [{"id": 1}]
    finally:
        await driver.disconnect()


@pytest.mark.asyncio
async def test_successful_rollback_hook_with_implicit_write_quarantines_connection(
    tmp_path, monkeypatch
):
    pool = SQLitePool(tmp_path / "rollback-hook.sqlite")
    driver = SQLiteProvider(str(pool.path), connection_pool=pool)
    await driver.connect()
    await driver.execute("CREATE TABLE items(id INTEGER PRIMARY KEY)")

    async def hook(*, committed):
        assert not committed
        await driver.execute("INSERT INTO items VALUES(2)")

    monkeypatch.setattr(driver.transaction_manager, "_emit_transaction_end", hook)
    try:
        with pytest.raises(ValueError, match="original"):
            async with driver.transaction():
                await driver.execute("INSERT INTO items VALUES(1)")
                raise ValueError("original")
        assert not driver.connection_manager.connected
        with pytest.raises(DatabaseConnectionError):
            async with driver.connection_manager.get_connection():
                pass
        async with aiosqlite.connect(pool.path) as observer:
            async with observer.execute("SELECT id FROM items") as cursor:
                assert await cursor.fetchall() == []
    finally:
        await driver.disconnect()
