"""Regression tests: DatabaseService.execute must COMMIT mutations.

Before the fix, ``DatabaseService.execute`` delegated every statement to
``execute_query`` (the SELECT path — cursor fetch, no commit). On SQLite
that left INSERT/UPDATE/DELETE inside an open implicit transaction that
was silently rolled back when the connection closed, unless a later
statement on the same connection happened to commit. Data written via
``service.execute`` could vanish on clean shutdown.

These tests boot a real SQLite-backed DatabaseService against a temp
file, write through ``execute``, shut the service down, and verify the
data with a fresh raw connection.
"""

from __future__ import annotations

import sqlite3

import pytest

from quadkit.sql.providers.database_service import DatabaseService


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "commit_test.db")


async def _booted_service(db_path: str) -> DatabaseService:
    service = DatabaseService(config=f"sqlite+aiosqlite:///{db_path}")
    await service.boot()
    return service


def _fresh_rows(db_path: str, sql: str) -> list:
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


class TestExecuteCommitsMutations:
    @pytest.mark.asyncio
    async def test_insert_via_execute_survives_shutdown(self, db_path):
        service = await _booted_service(db_path)
        await service.execute(
            "CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, v TEXT)", []
        )
        result = await service.execute(
            "INSERT INTO t (id, v) VALUES (?, ?)", ["a", "1"]
        )
        assert result.success is True
        await service.shutdown()

        assert _fresh_rows(db_path, "SELECT id, v FROM t") == [("a", "1")]

    @pytest.mark.asyncio
    async def test_upsert_via_execute_survives_shutdown(self, db_path):
        service = await _booted_service(db_path)
        await service.execute(
            "CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, v TEXT)", []
        )
        upsert = (
            "INSERT INTO t (id, v) VALUES (?, ?) "
            "ON CONFLICT (id) DO UPDATE SET v = excluded.v"
        )
        await service.execute(upsert, ["a", "1"])
        await service.execute(upsert, ["a", "2"])
        await service.shutdown()

        assert _fresh_rows(db_path, "SELECT id, v FROM t") == [("a", "2")]

    @pytest.mark.asyncio
    async def test_update_and_delete_via_execute_survive_shutdown(self, db_path):
        service = await _booted_service(db_path)
        await service.execute(
            "CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, v TEXT)", []
        )
        await service.execute(
            "INSERT INTO t (id, v) VALUES (?, ?), (?, ?)", ["a", "1", "b", "2"]
        )
        await service.execute("UPDATE t SET v = ? WHERE id = ?", ["9", "a"])
        await service.execute("DELETE FROM t WHERE id = ?", ["b"])
        await service.shutdown()

        assert _fresh_rows(db_path, "SELECT id, v FROM t") == [("a", "9")]

    @pytest.mark.asyncio
    async def test_insert_reports_real_rowcount(self, db_path):
        """The read path used to report row_count=0 for every INSERT."""
        service = await _booted_service(db_path)
        await service.execute(
            "CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, v TEXT)", []
        )
        result = await service.execute(
            "INSERT INTO t (id, v) VALUES (?, ?)", ["a", "1"]
        )
        await service.shutdown()
        assert result.row_count == 1

    @pytest.mark.asyncio
    async def test_select_via_execute_still_returns_rows(self, db_path):
        service = await _booted_service(db_path)
        await service.execute(
            "CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, v TEXT)", []
        )
        await service.execute("INSERT INTO t (id, v) VALUES (?, ?)", ["a", "1"])
        result = await service.execute("SELECT id, v FROM t WHERE id = ?", ["a"])
        await service.shutdown()
        assert result.rows == [{"id": "a", "v": "1"}]

    @pytest.mark.asyncio
    async def test_cte_select_via_execute_returns_rows(self, db_path):
        """WITH ... SELECT must stay on the read path."""
        service = await _booted_service(db_path)
        await service.execute(
            "CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, v TEXT)", []
        )
        await service.execute("INSERT INTO t (id, v) VALUES (?, ?)", ["a", "1"])
        result = await service.execute(
            "WITH x AS (SELECT id, v FROM t) SELECT * FROM x", []
        )
        await service.shutdown()
        assert result.rows == [{"id": "a", "v": "1"}]

    @pytest.mark.asyncio
    async def test_failed_write_returns_failed_result(self, db_path):
        service = await _booted_service(db_path)
        result = await service.execute(
            "INSERT INTO missing_table (id) VALUES (?)", ["a"]
        )
        await service.shutdown()
        assert result.success is False
        assert result.error_message

    @pytest.mark.asyncio
    async def test_write_inside_explicit_transaction_respects_rollback(
        self, db_path
    ):
        """Explicit transactions keep control of commit/rollback."""
        service = await _booted_service(db_path)
        await service.execute(
            "CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, v TEXT)", []
        )
        try:
            async with service.transaction():
                await service.execute(
                    "INSERT INTO t (id, v) VALUES (?, ?)", ["a", "1"]
                )
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        await service.shutdown()
        assert _fresh_rows(db_path, "SELECT id FROM t") == []
