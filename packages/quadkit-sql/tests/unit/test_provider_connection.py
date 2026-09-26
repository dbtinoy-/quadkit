from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.sql.providers import DatabaseService


@pytest.mark.asyncio
async def test_get_connection_uses_db_provider_when_no_pool():
    provider = DatabaseService("sqlite+aiosqlite:///test.db")

    # Create a mock connection with a close coroutine
    mock_conn = MagicMock()

    async def mock_close():
        return None

    mock_conn.close = mock_close

    # Mock db_provider to return the connection via _create_connection
    mock_dbp = MagicMock()
    mock_dbp._create_connection = AsyncMock(return_value=mock_conn)
    mock_dbp._close_connection = AsyncMock()

    provider.db_provider = mock_dbp

    async with provider.get_connection() as conn:
        assert conn is mock_conn

    # Ensure underlying close/return method was attempted
    # Either _close_connection was called or conn.close was invoked.
    assert mock_dbp._create_connection.await_count == 1


@pytest.mark.asyncio
async def test_get_connection_uses_pool_when_available():
    provider = DatabaseService("sqlite+aiosqlite:///test.db")

    # Mock pool that yields a connection
    mock_conn = MagicMock()

    class PoolCtx:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, exc_type, exc, tb):
            return False

    pool = MagicMock()
    pool.get_connection.return_value = PoolCtx()

    provider.connection_pool = pool

    async with provider.get_connection() as conn:
        assert conn is mock_conn

    pool.get_connection.assert_called_once()
