"""Regression tests: each SQL statement is logged exactly once.

Historically ``DatabaseOperationContext`` (used by ``execute_insert`` /
``execute_update`` / ``execute_delete``) emitted its own query-log entry in
``__aexit__`` while the inner ``QueryExecutor.execute_modify`` also logged the
same statement in its ``finally`` block — so every mutation showed up twice
in the console/file/memory query log with identical SQL and params.

The query executor is the single source of query-log emission; the operation
context only manages the connection, timing, and error normalisation.
"""

from __future__ import annotations

import pytest

from quadkit.sql.logging import MemoryQueryLogger
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.fixture
async def provider():
    """In-memory SQLite provider capturing query logs in memory."""
    db = SQLiteProvider(database_path=":memory:", query_logger=MemoryQueryLogger())
    await db.connect()
    await db.execute(
        "CREATE TABLE items ("
        "id TEXT PRIMARY KEY, "
        "name TEXT NOT NULL)"
    )
    return db


def _log_entries(provider, sql_prefix: str):
    logger = provider.query_executor.query_logger
    return [
        entry
        for entry in logger._entries
        if entry.sql.strip().upper().startswith(sql_prefix)
    ]


@pytest.mark.asyncio
async def test_insert_is_logged_exactly_once(provider) -> None:
    await provider.execute_insert("items", {"id": "row-1", "name": "one"})

    inserts = _log_entries(provider, "INSERT")
    assert len(inserts) == 1, [e.sql for e in inserts]
    assert inserts[0].success is True


@pytest.mark.asyncio
async def test_update_is_logged_exactly_once(provider) -> None:
    await provider.execute_insert("items", {"id": "row-2", "name": "before"})
    await provider.execute_update("items", {"name": "after"}, "id = ?", ["row-2"])

    updates = _log_entries(provider, "UPDATE")
    assert len(updates) == 1, [e.sql for e in updates]
    assert updates[0].success is True


@pytest.mark.asyncio
async def test_delete_is_logged_exactly_once(provider) -> None:
    await provider.execute_insert("items", {"id": "row-3", "name": "gone"})
    await provider.execute_delete("items", "id = ?", ["row-3"])

    deletes = _log_entries(provider, "DELETE")
    assert len(deletes) == 1, [e.sql for e in deletes]
    assert deletes[0].success is True


@pytest.mark.asyncio
async def test_select_is_logged_exactly_once(provider) -> None:
    await provider.execute_insert("items", {"id": "row-4", "name": "four"})
    await provider.execute_query("SELECT * FROM items WHERE id = ?", ["row-4"])

    selects = _log_entries(provider, "SELECT * FROM ITEMS")
    assert len(selects) == 1, [e.sql for e in selects]
    assert selects[0].success is True


@pytest.mark.asyncio
async def test_failed_modify_is_logged_exactly_once(provider) -> None:
    from quadkit.sql.exceptions import DatabaseError

    await provider.execute_insert("items", {"id": "row-5", "name": "five"})
    with pytest.raises(DatabaseError):
        # Primary-key violation
        await provider.execute_insert("items", {"id": "row-5", "name": "dup"})

    inserts = _log_entries(provider, "INSERT")
    # One successful insert + one failed insert — each logged once.
    assert len(inserts) == 2, [(e.sql, e.success) for e in inserts]
    assert sorted(e.success for e in inserts) == [False, True]
