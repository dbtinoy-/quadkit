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


@pytest.mark.asyncio
async def test_execute_update_moves_a_column_with_delta():
    """A ``Delta`` writes ``col = col + ?``, not the object it is given.

    The point of the type is that the movement happens inside the statement:
    the value read back is the stored value plus the delta, applied to the row
    as it is at write time rather than as the caller read it.
    """
    from quadkit.contracts.data.identifiers import Delta

    p = SQLiteProvider(":memory:")
    await p.connect()
    await p.execute_query(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY, quota INTEGER NOT NULL)",
    )
    await p.execute_insert("accounts", {"id": 1, "quota": 100})

    decreased = await p.execute_update(
        "accounts", {"quota": Delta("quota", -30)}, '"id" = ?', [1]
    )
    assert decreased.success is True
    assert decreased.affected_rows == 1

    increased = await p.execute_update(
        "accounts", {"quota": Delta("quota", 5)}, '"id" = ?', [1]
    )
    assert increased.success is True

    rows = await p.execute_query("SELECT quota FROM accounts WHERE id = 1")
    assert rows.rows[0]["quota"] == 75


@pytest.mark.asyncio
async def test_execute_update_mixes_delta_and_plain_values():
    """A plain assignment and a move can share one statement, in column order."""
    from quadkit.contracts.data.identifiers import Delta

    p = SQLiteProvider(":memory:")
    await p.connect()
    await p.execute_query(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY, quota INTEGER NOT NULL, label TEXT)",
    )
    await p.execute_insert("accounts", {"id": 1, "quota": 100, "label": "old"})

    await p.execute_update(
        "accounts",
        {"label": "new", "quota": Delta("quota", 10)},
        '"id" = ?',
        [1],
    )

    rows = await p.execute_query("SELECT quota, label FROM accounts WHERE id = 1")
    assert rows.rows[0]["quota"] == 110
    assert rows.rows[0]["label"] == "new"
