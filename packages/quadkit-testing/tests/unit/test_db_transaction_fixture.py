"""Tests for the db_transaction and database_provider fixtures.

Verifies:
- ``database_provider`` returns ``None`` by default (skip-safe default)
- ``db_transaction`` skips gracefully when no real provider is configured
- ``db_transaction`` opens a scoped context, executes BEGIN before yield,
  and always executes ROLLBACK in teardown
- Rollback always occurs, even when the test body raises an exception
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_provider() -> tuple[Any, Any, list[str]]:
    """Build a mock DatabaseProviderProtocol with scoped_context support.

    Returns:
        Tuple of (provider_mock, connection_mock, executed_sql_list).
    """
    provider = MagicMock()
    conn = MagicMock()
    executed: list[str] = []

    async def execute(sql: str, *args: Any) -> None:
        executed.append(sql)

    conn.execute = execute
    conn._executed = executed

    @asynccontextmanager
    async def scoped_context():  # type: ignore[return]
        yield

    provider.scoped_context = scoped_context
    provider.get_scoped_connection = AsyncMock(return_value=conn)

    return provider, conn, executed


def _raw_db_transaction(provider: Any) -> Any:
    """Return the unwrapped async generator for ``db_transaction``.

    ``db_transaction`` is decorated by pytest. ``__wrapped__`` exposes the
    original async generator function so we can drive it manually in tests.
    """
    from quadkit.testing.fixtures.db import db_transaction

    raw = db_transaction.__wrapped__  # type: ignore[attr-defined]
    return raw(provider)


# ---------------------------------------------------------------------------
# Tests: database_provider placeholder
# ---------------------------------------------------------------------------


class TestDatabaseProviderPlaceholder:
    """The default database_provider fixture returns None."""

    def test_default_fixture_returns_none(
        self, database_provider: Any
    ) -> None:
        """database_provider yields None when not overridden in conftest."""
        assert database_provider is None


# ---------------------------------------------------------------------------
# Tests: db_transaction skip behaviour (no real provider)
# ---------------------------------------------------------------------------


class TestDbTransactionSkip:
    """db_transaction skips when database_provider is None."""

    @pytest.mark.asyncio
    async def test_skips_when_provider_is_none(self) -> None:
        """db_transaction raises Skipped when no provider is configured."""
        gen = _raw_db_transaction(None)
        with pytest.raises(pytest.skip.Exception):
            await gen.__anext__()


# ---------------------------------------------------------------------------
# Tests: db_transaction with a real (mocked) provider — fixture injection
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_provider() -> Any:
    """A mock DatabaseProviderProtocol for use in rollback tests."""
    provider, _conn, _executed = _make_mock_provider()
    return provider


class TestDbTransactionWithProvider:
    """db_transaction yields the connection after executing BEGIN."""

    # Class-level override: supply the mock provider for tests in this class.
    @pytest.fixture
    def database_provider(self, mock_db_provider: Any) -> Any:
        """Override the placeholder fixture for this class's tests."""
        return mock_db_provider

    @pytest.mark.asyncio
    async def test_yields_connection(
        self, db_transaction: Any, mock_db_provider: Any
    ) -> None:
        """db_transaction yields the database connection, not the provider."""
        assert db_transaction is mock_db_provider.get_scoped_connection.return_value

    @pytest.mark.asyncio
    async def test_get_scoped_connection_called_before_yield(
        self, db_transaction: Any, mock_db_provider: Any
    ) -> None:
        """get_scoped_connection is called before the test body executes."""
        mock_db_provider.get_scoped_connection.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_commit_never_called(
        self, db_transaction: Any, mock_db_provider: Any
    ) -> None:
        """COMMIT is never executed — rollback is unconditional."""
        # db_transaction IS the connection; _executed tracks all SQL calls.
        # At this point (during test body) only BEGIN has been executed.
        assert "COMMIT" not in db_transaction._executed


# ---------------------------------------------------------------------------
# Tests: rollback — driving the raw generator manually for full coverage
# ---------------------------------------------------------------------------


class TestDbTransactionRollback:
    """Verify ROLLBACK is executed: on clean close and on exception."""

    @pytest.mark.asyncio
    async def test_rollback_on_clean_close(self) -> None:
        """ROLLBACK is executed when the generator is closed normally."""
        provider, _conn, executed = _make_mock_provider()
        gen = _raw_db_transaction(provider)

        await gen.__anext__()
        await gen.aclose()

        assert "BEGIN" in executed
        assert "ROLLBACK" in executed
        assert "COMMIT" not in executed

    @pytest.mark.asyncio
    async def test_rollback_on_test_exception(self) -> None:
        """ROLLBACK is executed even when the test body raises."""
        provider, _conn, executed = _make_mock_provider()
        gen = _raw_db_transaction(provider)

        await gen.__anext__()
        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("test failure"))

        assert "ROLLBACK" in executed
        assert "COMMIT" not in executed

    @pytest.mark.asyncio
    async def test_rollback_before_exception_propagates(self) -> None:
        """Rollback is performed before the exception propagates to the caller."""
        call_order: list[str] = []

        @asynccontextmanager
        async def scoped_context():  # type: ignore[return]
            yield

        provider = MagicMock()
        provider.scoped_context = scoped_context
        conn = MagicMock()

        async def execute(sql: str, *args: Any) -> None:
            call_order.append(sql)

        conn.execute = execute
        provider.get_scoped_connection = AsyncMock(return_value=conn)

        gen = _raw_db_transaction(provider)
        await gen.__anext__()
        try:
            await gen.athrow(ValueError("boom"))
        except ValueError:
            pass

        assert call_order == ["BEGIN", "ROLLBACK"]

    @pytest.mark.asyncio
    async def test_yielded_value_is_connection(self) -> None:
        """The value yielded by the generator is the connection, not provider."""
        provider, conn, _ = _make_mock_provider()
        gen = _raw_db_transaction(provider)

        yielded = await gen.__anext__()
        assert yielded is conn

        await gen.aclose()

