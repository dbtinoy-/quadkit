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
        """Data inserted via execute is retrievable via fetch_one."""
        provider = await self.create_provider()
        async with provider.scoped_context():
            conn = await provider.get_scoped_connection()
            await conn.execute(
                "CREATE TEMPORARY TABLE _compliance_rw "
                "(id INTEGER PRIMARY KEY, val TEXT)"
            )
            await conn.execute("INSERT INTO _compliance_rw(id, val) VALUES(1, 'hello')")
            row = await conn.fetch_one("SELECT val FROM _compliance_rw WHERE id = 1")
            assert row is not None
            val = row["val"] if hasattr(row, "__getitem__") else row.val
            assert val == "hello"

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

            row = await conn.fetch_one("SELECT val FROM _compliance_tx WHERE id = 42")
            assert row is None
