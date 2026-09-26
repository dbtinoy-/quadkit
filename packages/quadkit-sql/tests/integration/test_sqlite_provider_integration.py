"""In-process SQLite provider CRUD tests.

Runs entirely against an in-memory SQLite database — no live PostgreSQL or
Docker Compose stack is required, so this file belongs to the default
``-m "not integration"`` suite.
"""

import pytest

from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.mark.asyncio
async def test_sqlite_provider_basic_crud_and_schema():
    p = SQLiteProvider(":memory:")

    await p.connect()

    # create table
    await p.execute_query(
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)",
    )

    # insert a row and check InsertResult
    ins = await p.execute_insert("users", {"name": "alice"})
    assert ins.success is True
    assert ins.affected_rows == 1
    assert ins.inserted_id is not None

    # select rows
    qres = await p.execute_query("SELECT id, name FROM users")
    assert qres.row_count == 1
    assert qres.rows[0]["name"] == "alice"

    # get table columns
    cols = await p.get_table_columns("users")
    assert any(c["name"] == "id" for c in cols)

    # table exists should be True
    assert await p.table_exists("users") is True

    # test transaction commit
    async with p.transaction():
        await p.execute_insert("users", {"name": "bob"})
    qres2 = await p.execute_query(
        "SELECT id, name FROM users WHERE name = ?", ["bob"],
    )  # should be committed
    assert any(r["name"] == "bob" for r in qres2.rows)

    # test transaction rollback
    try:
        async with p.transaction():
            await p.execute_insert("users", {"name": "charlie"})
            raise RuntimeError("force rollback")
    except RuntimeError:
        pass

    qres3 = await p.execute_query(
        "SELECT id, name FROM users WHERE name = ?", ["charlie"],
    )  # rolled back
    assert qres3.row_count == 0

    # health check
    h = await p.health_check()
    assert h.status.value == "healthy"

    await p.disconnect()
