"""Tests for database instrumentation."""

import pytest

pytest.importorskip("opentelemetry", reason="Requires opentelemetry")
from unittest.mock import AsyncMock, MagicMock
from opentelemetry import metrics, trace

from quadkit.monitor.instrumentation.database import instrument_database


@pytest.fixture
def mock_db_provider():
    provider = MagicMock()
    provider.url = "sqlite:///test.db"
    provider.config = MagicMock()
    provider.config.name = "test_db"
    provider.execute = AsyncMock()
    provider.execute_query = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_instrument_database_execute(mock_db_provider):
    """Test instrumenting database execute."""
    # Setup mock result
    mock_result = MagicMock()
    mock_result.success = True
    mock_db_provider.execute.return_value = mock_result
    
    instrument_database(mock_db_provider)
    
    # Should not re-instrument
    instrument_database(mock_db_provider)
    
    result = await mock_db_provider.execute("SELECT * FROM users")
    assert result == mock_result

@pytest.mark.asyncio
async def test_instrument_database_execute_error(mock_db_provider):
    """Test instrumenting database execute with error status."""
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.error_message = "SQL Error"
    mock_db_provider.execute.return_value = mock_result
    
    instrument_database(mock_db_provider)
    
    result = await mock_db_provider.execute("SELECT * FROM invalid", {"id": 1})
    assert result == mock_result

@pytest.mark.asyncio
async def test_instrument_database_execute_exception(mock_db_provider):
    """Test instrumenting database execute with exception."""
    mock_db_provider.execute.side_effect = RuntimeError("connection lost")
    
    instrument_database(mock_db_provider)
    
    with pytest.raises(RuntimeError, match="connection lost"):
        await mock_db_provider.execute("SELECT 1")

@pytest.mark.asyncio
async def test_instrument_database_postgres_url():
    """Test postgres url detection."""
    provider = MagicMock()
    provider.url = "postgresql://user:pass@localhost:5432/db"
    provider.execute = AsyncMock()
    
    instrument_database(provider)
    await provider.execute("SELECT 1")

@pytest.mark.asyncio
async def test_instrument_database_mysql_url():
    """Test mysql url detection."""
    provider = MagicMock()
    provider.url = "mysql://user:pass@localhost:3306/db"
    provider.execute = AsyncMock()
    
    instrument_database(provider)
    await provider.execute("SELECT 1")

@pytest.mark.asyncio
async def test_instrument_database_other_url():
    """Test other url detection."""
    provider = MagicMock()
    provider.url = "unknown://localhost/db"
    provider.execute = AsyncMock()
    
    instrument_database(provider)
    await provider.execute("SELECT 1")

@pytest.mark.asyncio
async def test_instrument_database_query(mock_db_provider):
    """Test instrumenting database query."""
    instrument_database(mock_db_provider)
    
    await mock_db_provider.execute_query("SELECT * FROM users")

@pytest.mark.asyncio
async def test_instrument_database_query_exception(mock_db_provider):
    """Test instrumenting database query with exception."""
    mock_db_provider.execute_query.side_effect = ConnectionError("timeout")
    
    instrument_database(mock_db_provider)
    
    with pytest.raises(ConnectionError, match="timeout"):
        await mock_db_provider.execute_query("SELECT 1")
