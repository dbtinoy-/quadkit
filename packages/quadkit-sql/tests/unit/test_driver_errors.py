import sqlite3

import pytest

from quadkit.sql.backends.mysql import MySQLConnection
from quadkit.sql.backends.postgres import PostgresConnection
from quadkit.sql.backends.sqlite import SQLiteConnection
from quadkit.sql.exceptions import (
    DatabaseError,
    QueryError,
)

try:
    import asyncpg

    _asyncpg_error: type = asyncpg.PostgresError
except ImportError:
    _asyncpg_error = DatabaseError

try:
    import aiomysql

    _aiomysql_error: type = aiomysql.Error
except ImportError:
    _aiomysql_error = DatabaseError


class _BadExec:
    async def execute(self, *args, **kwargs):
        raise sqlite3.OperationalError("boom")

    async def commit(self):
        pass


class _BadFetch:
    async def fetchrow(self, *args, **kwargs):
        raise _asyncpg_error("boom")

    async def fetch(self, *args, **kwargs):
        raise _asyncpg_error("boom")


class _BadCursor:
    async def __aenter__(self):
        raise _aiomysql_error("cursor fail")

    async def __aexit__(self, exc_type, exc, tb):
        pass


class _BadMySQLConn:
    def __init__(self):
        self.affected_rows = 0

    async def execute(self, *args, **kwargs):
        raise _aiomysql_error("boom")

    async def cursor(self):
        return _BadCursor()

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_sqlite_query_failure_logs_and_raises(caplog):
    caplog.set_level("ERROR")
    conn = SQLiteConnection(_BadExec())

    with pytest.raises(DatabaseError):
        await conn.execute("SELECT 1")

    assert conn is not None


@pytest.mark.asyncio
async def test_postgres_query_failure_logs_and_raises(caplog):
    caplog.set_level("ERROR")
    conn = PostgresConnection(_BadFetch())

    with pytest.raises(QueryError):
        await conn.fetch_one("SELECT 1")

    assert conn is not None


@pytest.mark.asyncio
async def test_mysql_query_failure_logs_and_raises(caplog):
    caplog.set_level("ERROR")
    conn = MySQLConnection(_BadMySQLConn())

    with pytest.raises(QueryError):
        await conn.execute("SELECT 1")

    assert conn is not None
