"""Tests for the database test client and bed (in-memory simulation).

Covers :class:`DatabaseTestClient`'s full surface — connection lifecycle,
context manager, query/execute simulation, table management, and data
insertion — plus the :class:`DatabaseTestBed` convenience layer.
"""

from __future__ import annotations

import pytest

from quadkit.testing.clients.db.bed import DatabaseTestBed
from quadkit.testing.clients.db.client import DatabaseTestClient


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


async def test_context_manager_connects_and_disconnects() -> None:
    client = DatabaseTestClient()
    assert client._connected is False
    async with client:
        assert client._connected is True
        assert client._pool == "mock_pool"
        assert client._connection == "mock_connection"
    assert client._connected is False
    assert client._pool is None
    assert client._connection is None


async def test_connect_and_disconnect() -> None:
    client = DatabaseTestClient()
    await client.connect()
    assert client._connected is True
    await client.disconnect()
    assert client._connected is False
    assert client._tables_created == []


def test_check_connected_raises_when_disconnected() -> None:
    client = DatabaseTestClient()
    with pytest.raises(RuntimeError, match="Not connected"):
        client._check_connected()


# ---------------------------------------------------------------------------
# Query / execute simulation
# ---------------------------------------------------------------------------


async def test_execute_query_returns_empty_list() -> None:
    async with DatabaseTestClient() as client:
        assert await client.execute_query("SELECT 1", [1]) == []


async def test_execute_fetch_returns_seeded_rows() -> None:
    async with DatabaseTestClient() as client:
        await client.create_table("users", {"id": "int"})
        await client.insert_data("users", [{"id": 1, "name": "a"}])

        rows = await client.execute("SELECT * FROM users")
        assert rows == [{"id": 1, "name": "a"}]

        # Unknown table returns empty list
        assert await client.execute("SELECT * FROM missing") == []


async def test_execute_no_fetch_returns_rowcount() -> None:
    async with DatabaseTestClient() as client:
        assert await client.execute("INSERT INTO t VALUES (1)", fetch=False) == 1


def test_extract_table_from_query() -> None:
    client = DatabaseTestClient()
    assert client._extract_table_from_query("SELECT * FROM users WHERE id = 1") == (
        "users"
    )
    assert client._extract_table_from_query("DELETE FROM t1;") == "t1"
    assert client._extract_table_from_query("INSERT INTO t2 (a) VALUES (1)") is None


# ---------------------------------------------------------------------------
# Table management
# ---------------------------------------------------------------------------


async def test_create_drop_clear_and_count() -> None:
    async with DatabaseTestClient() as client:
        await client.create_table("orders", "id INTEGER")
        assert "orders" in client._tables_created

        await client.insert_data("orders", [{"id": 1}])
        assert await client.get_table_count("orders") == 1
        assert await client.get_table_count("absent") == 0

        await client.clear_table("orders")
        assert await client.get_table_count("orders") == 0

        await client.drop_table("orders")
        assert "orders" not in client._tables_created
        assert await client.get_table_count("orders") == 0

        # drop of an unknown table is a no-op
        await client.drop_table("never-existed")


async def test_insert_data_dict_and_list() -> None:
    async with DatabaseTestClient() as client:
        assert await client.insert_data("t", {"a": 1}) == 1
        assert await client.insert("t", [{"a": 2}, {"a": 3}]) == 2
        assert await client.get_table_count("t") == 3


async def test_cleanup_drops_tracked_state() -> None:
    client = DatabaseTestClient(auto_cleanup=False)
    await client.connect()
    await client.create_table("tmp", "id INTEGER")
    await client.insert_data("tmp", [{"id": 1}])
    await client.cleanup()
    assert client._tables_created == []
    assert client._table_data == {}
    await client.disconnect()


# ---------------------------------------------------------------------------
# DatabaseTestBed
# ---------------------------------------------------------------------------


async def test_bed_context_and_convenience_methods() -> None:
    async with DatabaseTestBed() as bed:
        assert bed.client._connected is True
        await bed.create_test_table("products", "id INTEGER, name TEXT")
        assert "products" in bed.client._tables_created

        await bed.seed_test_data("products", [{"id": 1, "name": "widget"}])
        assert await bed.client.get_table_count("products") == 1

        await bed.clear_test_data("products")
        assert await bed.client.get_table_count("products") == 0

    assert bed.client._connected is False


def test_bed_custom_connection_string_and_cleanup_flag() -> None:
    bed = DatabaseTestBed(
        name="custom",
        connection_string="sqlite:///test.db",
        auto_cleanup=False,
    )
    assert bed.connection_string == "sqlite:///test.db"
    assert bed.auto_cleanup is False
    assert bed.client.connection_string == "sqlite:///test.db"
