"""Regression tests for JSON-shaped parameter binding in the generic CRUD layer.

Relational drivers cannot bind Python ``dict``/``list`` objects directly;
``CrudOperations`` must encode them as JSON text so stores such as
``APIKeySqlRepository`` (``scopes``), ``SqlDeliveryStore`` (``message``) and
the auth users store (``roles``/``permissions``/``profile``) can persist.
"""

from __future__ import annotations

import pytest

from quadkit.serialization import loads
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.fixture
async def provider():
    """In-memory SQLite provider with a JSON-ish test table."""
    db = SQLiteProvider(database_path=":memory:")
    await db.connect()
    await db.execute(
        "CREATE TABLE test_payload ("
        "id TEXT PRIMARY KEY, "
        "labels TEXT, "
        "metadata TEXT, "
        "name TEXT NOT NULL)"
    )
    return db


@pytest.mark.asyncio
async def test_execute_insert_binds_dict_and_list_as_json_text(provider) -> None:
    """dict/list payload values are JSON-encoded before driver binding."""
    await provider.execute_insert(
        "test_payload",
        {
            "id": "row-1",
            "labels": ["a", "b"],
            "metadata": {"retries": 3, "enabled": True},
            "name": "plain",
        },
    )

    result = await provider.execute_query(
        "SELECT labels, metadata, name FROM test_payload WHERE id = ?", ["row-1"]
    )
    row = result.rows[0]
    assert row["name"] == "plain"
    assert loads(row["labels"]) == ["a", "b"]
    assert loads(row["metadata"]) == {"retries": 3, "enabled": True}


@pytest.mark.asyncio
async def test_execute_update_binds_dict_as_json_text(provider) -> None:
    """UPDATE payload dict values are JSON-encoded as well."""
    await provider.execute_insert(
        "test_payload",
        {"id": "row-2", "labels": "[]", "metadata": "{}", "name": "before"},
    )
    await provider.execute_update(
        "test_payload",
        {"metadata": {"note": "updated"}},
        "id = ?",
        ["row-2"],
    )

    result = await provider.execute_query(
        "SELECT metadata FROM test_payload WHERE id = ?", ["row-2"]
    )
    assert loads(result.rows[0]["metadata"]) == {"note": "updated"}


@pytest.mark.asyncio
async def test_execute_insert_round_trips_scopes_like_apikey_repository(
    provider,
) -> None:
    """The exact shape used by APIKeySqlRepository.insert (list of scopes)."""
    await provider.execute_insert(
        "test_payload",
        {
            "id": "key-1",
            "labels": ["users:read", "users:write"],
            "metadata": "{}",
            "name": "api-key",
        },
    )
    rows = await provider.execute_query(
        "SELECT labels FROM test_payload WHERE id = ?", ["key-1"]
    )
    assert loads(rows.rows[0]["labels"]) == ["users:read", "users:write"]
