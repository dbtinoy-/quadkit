"""Contract compliance suite for ``DatabaseProviderProtocol`` implementations.

Subclass :class:`DatabaseProviderCompliance` and implement
:meth:`create_provider` to verify any database provider satisfies the
``DatabaseProviderProtocol`` contract::

    from quadkit.testing.compliance import DatabaseProviderCompliance

    class TestMyDatabaseProvider(DatabaseProviderCompliance):
        async def create_provider(self):
            return MyDatabaseProvider(dsn="sqlite+aiosqlite:///:memory:")
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pytest

__all__ = ["DatabaseProviderCompliance"]


class DatabaseProviderCompliance:
    """Reusable test suite for any ``DatabaseProviderProtocol`` implementation.

    Subclass and implement :meth:`create_provider`:

    .. code-block:: python

        class TestMyProvider(DatabaseProviderCompliance):
            async def create_provider(self):
                return MyDatabaseProvider(dsn="sqlite+aiosqlite:///:memory:")
    """

    @abstractmethod
    async def create_provider(self) -> Any:
        """Return a ready-to-use provider instance under test."""
        ...

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check_returns_result(self) -> None:
        """health_check returns a HealthCheckResult."""
        provider = await self.create_provider()
        result = await provider.health_check(timeout=5.0)
        assert result is not None
        assert hasattr(result, "status")

    # ------------------------------------------------------------------
    # Scoped context and connection
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_scoped_context_provides_connection(self) -> None:
        """get_scoped_connection returns a connection within a scoped context."""
        provider = await self.create_provider()
        async with provider.scoped_context():
            conn = await provider.get_scoped_connection()
            assert conn is not None

    @pytest.mark.asyncio
    async def test_scoped_context_is_reentrant(self) -> None:
        """Nested scoped_context blocks do not raise."""
        provider = await self.create_provider()
        async with provider.scoped_context():
            async with provider.scoped_context():
                conn = await provider.get_scoped_connection()
                assert conn is not None

    # ------------------------------------------------------------------
    # Execute and fetch
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_execute_ddl(self) -> None:
        """execute can run DDL statements without error."""
        provider = await self.create_provider()
        async with provider.scoped_context():
            conn = await provider.get_scoped_connection()
            await conn.execute(
                "CREATE TEMPORARY TABLE _compliance_check (id INTEGER PRIMARY KEY)"
            )

    @pytest.mark.asyncio
    async def test_execute_and_fetch(self) -> None:
        """Data inserted via execute is retrievable via the contract's fetchrow."""
        provider = await self.create_provider()
        async with provider.scoped_context():
            conn = await provider.get_scoped_connection()
            await conn.execute(
                "CREATE TEMPORARY TABLE _compliance_rw "
                "(id INTEGER PRIMARY KEY, val TEXT)"
            )
            await conn.execute("INSERT INTO _compliance_rw(id, val) VALUES(1, 'hello')")
            row = await conn.fetchrow("SELECT val FROM _compliance_rw WHERE id = 1")
            assert row is not None
            val = row["val"] if hasattr(row, "__getitem__") else row.val
            assert val == "hello"

    # ------------------------------------------------------------------
    # Provider-level CRUD surface
    #
    # The connection-level tests above cover the ``ConnectionProtocol`` path.
    # The framework's own stores (inbox, delivery state, audit) do not use it:
    # they provision a table and write rows through the provider-level
    # ``execute_query``/``execute_insert`` surface. Two contract rules live
    # only there, and both have been violated in practice by a provider that
    # passed the connection-level suite:
    #
    # 1. a statement that returns no rows (DDL) is a success with no rows, and
    # 2. JSON-shaped bind values (``dict``/``list``) are encoded before binding.
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_execute_query_ddl_is_not_a_failure(self) -> None:
        """A row-less statement through execute_query succeeds with no rows.

        Stores provision their tables this way (``CREATE TABLE IF NOT
        EXISTS``); an implementation that reports "no result set" as failure
        makes provisioning look broken even though the table was created.
        """
        provider = await self.create_provider()
        result = await provider.execute_query(
            "CREATE TABLE IF NOT EXISTS _compliance_ddl (id INTEGER PRIMARY KEY)"
        )
        assert result.success is True
        assert result.rows == []

    @pytest.mark.asyncio
    async def test_execute_insert_binds_json_shaped_values(self) -> None:
        """A ``dict``/``list`` column value round-trips as JSON text.

        Relational drivers cannot bind a Python container. Stores that declare
        JSON columns — an inbox message's ``metadata``, a delivery record's
        ``message`` — pass containers, so the provider encodes them and the
        value comes back as the JSON text the schema stores.
        """
        provider = await self.create_provider()
        created = await provider.execute_query(
            "CREATE TABLE IF NOT EXISTS _compliance_json "
            "(id TEXT PRIMARY KEY, metadata TEXT NOT NULL DEFAULT '{}')"
        )
        assert created.success is True

        inserted = await provider.execute_insert(
            "_compliance_json",
            {"id": "row-1", "metadata": {"order_id": "7", "tags": ["a", "b"]}},
        )
        assert inserted.success is True, inserted.error_message

        fetched = await provider.execute_query(
            "SELECT metadata FROM _compliance_json WHERE id = ?", ["row-1"]
        )
        assert fetched.success is True, fetched.error_message
        assert fetched.rows, "the inserted row was not readable"
        stored = fetched.rows[0]["metadata"]
        assert stored == '{"order_id":"7","tags":["a","b"]}'

    @pytest.mark.asyncio
    async def test_execute_update_binds_json_shaped_values(self) -> None:
        """``execute_update`` encodes JSON-shaped values in its data mapping."""
        provider = await self.create_provider()
        await provider.execute_query(
            "CREATE TABLE IF NOT EXISTS _compliance_json_update "
            "(id TEXT PRIMARY KEY, metadata TEXT NOT NULL DEFAULT '{}')"
        )
        await provider.execute_insert(
            "_compliance_json_update", {"id": "row-1", "metadata": "{}"}
        )

        updated = await provider.execute_update(
            "_compliance_json_update",
            {"metadata": {"patched": True}},
            "id = ?",
            ["row-1"],
        )
        assert updated.success is True, updated.error_message

        fetched = await provider.execute_query(
            "SELECT metadata FROM _compliance_json_update WHERE id = ?", ["row-1"]
        )
        assert fetched.rows[0]["metadata"] == '{"patched":true}'

    # ------------------------------------------------------------------
    # Transaction rollback
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_transaction_rollback_discards_writes(self) -> None:
        """Data written inside a rolled-back transaction is not persisted."""
        provider = await self.create_provider()
        async with provider.scoped_context():
            conn = await provider.get_scoped_connection()
            await conn.execute(
                "CREATE TEMPORARY TABLE _compliance_tx "
                "(id INTEGER PRIMARY KEY, val TEXT)"
            )
            # Write inside a transaction then roll back
            await conn.execute("BEGIN")
            await conn.execute(
                "INSERT INTO _compliance_tx(id, val) VALUES(42, 'should_vanish')"
            )
            await conn.execute("ROLLBACK")

            row = await conn.fetchrow("SELECT val FROM _compliance_tx WHERE id = 42")
            assert row is None
