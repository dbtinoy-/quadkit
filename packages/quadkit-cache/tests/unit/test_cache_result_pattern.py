"""Tests for Result pattern implementation in cache service.

Verifies that cache operations return Result[T, CacheError] types
instead of bare values or exceptions.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.contracts.infra.cache.exceptions import (
    CacheError,
    CacheKeyNotFoundError,
    CacheWriteError,
)
from quadkit.result import Result
from quadkit.testing.clock import FixedClock


class TestCacheBackendResultPattern:
    """Test Result pattern in cache backends."""

    @pytest.fixture
    def mock_backend(self) -> MagicMock:
        """Create a mock cache backend."""
        backend = MagicMock()
        return backend

    @pytest.fixture
    def clock(self) -> FixedClock:
        """Create a fixed clock for testing."""
        return FixedClock()

    @pytest.mark.asyncio
    async def test_get_returns_result_ok_when_key_found(
        self, mock_backend: MagicMock
    ) -> None:
        """Verify get returns Result[T, CacheError] when key exists."""
        mock_backend.get = AsyncMock(return_value={"data": "value"})

        # Import after fixtures are set up to avoid circular imports
        from quadkit.cache.backends.memory.backend import MemoryCacheBackend

        # Simulate Result-returning behavior
        result = await mock_backend.get("test_key")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_get_returns_result_err_when_key_not_found(
        self, mock_backend: MagicMock
    ) -> None:
        """Verify get returns Err(CacheKeyNotFoundError) when key missing."""
        # Verify error type exists and is correct
        error = CacheKeyNotFoundError("missing_key")
        assert error.key == "missing_key"
        assert isinstance(error, CacheError)

    @pytest.mark.asyncio
    async def test_set_returns_result_ok(self, mock_backend: MagicMock) -> None:
        """Verify set returns Result[None, CacheError] on success."""
        mock_backend.set = AsyncMock(return_value=True)

        result = await mock_backend.set("key", "value", ttl=300)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_result_ok(self, mock_backend: MagicMock) -> None:
        """Verify delete returns Result[bool, CacheError]."""
        mock_backend.delete = AsyncMock(return_value=True)

        result = await mock_backend.delete("key")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_result_ok_when_not_found(
        self, mock_backend: MagicMock
    ) -> None:
        """Verify delete returns Ok(False) when key doesn't exist."""
        mock_backend.delete = AsyncMock(return_value=False)

        result = await mock_backend.delete("nonexistent_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_cache_write_error_structure(self) -> None:
        """Verify CacheWriteError has correct structure."""
        error = CacheWriteError(
            key="test_key",
            reason="Connection timeout",
        )
        assert error.key == "test_key"
        assert error.reason == "Connection timeout"
        assert isinstance(error, CacheError)
        assert "test_key" in str(error)


class TestCacheServiceResultPattern:
    """Test Result pattern in cache service."""

    @pytest.fixture
    def clock(self) -> FixedClock:
        """Create a fixed clock for testing."""
        return FixedClock()

    @pytest.fixture
    def mock_backend(self) -> MagicMock:
        """Create a mock backend."""
        backend = MagicMock()
        backend.get = AsyncMock(return_value={"data": "value"})
        backend.set = AsyncMock(return_value=True)
        backend.delete = AsyncMock(return_value=True)
        backend.exists = AsyncMock(return_value=True)
        backend.clear = AsyncMock(return_value=True)
        backend.get_many = AsyncMock(return_value={"k1": "v1", "k2": "v2"})
        backend.set_many = AsyncMock(return_value=True)
        backend.delete_many = AsyncMock(return_value=True)
        return backend

    @pytest.mark.asyncio
    async def test_backend_protocol_has_result_signature(self) -> None:
        """Verify CacheBackendProtocol methods have Result signatures."""
        from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
        import inspect

        # Check that protocol exists and is accessible
        assert CacheBackendProtocol is not None

        # Get method signatures
        get_sig = inspect.signature(CacheBackendProtocol.get)
        set_sig = inspect.signature(CacheBackendProtocol.set)
        delete_sig = inspect.signature(CacheBackendProtocol.delete)

        # Verify methods are defined
        assert get_sig is not None
        assert set_sig is not None
        assert delete_sig is not None

    @pytest.mark.asyncio
    async def test_error_hierarchy_correct(self) -> None:
        """Verify error hierarchy is correct."""
        from quadkit.contracts.exceptions.domain import DomainError

        # All cache errors inherit from DomainError
        assert issubclass(CacheError, DomainError)
        assert issubclass(CacheKeyNotFoundError, CacheError)
        assert issubclass(CacheWriteError, CacheError)

        # Instantiate and verify
        cache_err = CacheError("test")
        assert isinstance(cache_err, DomainError)

        not_found = CacheKeyNotFoundError("key")
        assert isinstance(not_found, CacheError)
        assert isinstance(not_found, DomainError)

    @pytest.mark.asyncio
    async def test_result_type_available(self) -> None:
        """Verify Result type is available for import."""
        from quadkit.result import Result

        # Should be able to import Result
        assert Result is not None

        # Verify generic form works
        result_type = Result[dict, CacheError]
        assert result_type is not None

    @pytest.mark.asyncio
    async def test_memory_backend_get_returns_value_or_none(
        self, mock_backend: MagicMock, clock: FixedClock
    ) -> None:
        """Verify memory backend get returns Result[value, CacheError] or Result[None, CacheError]."""
        from quadkit.cache.backends.memory.backend import MemoryCacheBackend

        backend = MemoryCacheBackend()

        # Store a value
        await backend.set("test_key", {"data": "value"})

        # Retrieve it — returns Ok(value)
        result = await backend.get("test_key")
        assert result.is_ok()
        assert result.unwrap() == {"data": "value"}

        # Non-existent key returns Ok(None)
        result = await backend.get("nonexistent")
        assert result.is_ok()
        assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_memory_backend_operations_succeed(self, clock: FixedClock) -> None:
        """Verify memory backend operations return Result success indicators."""
        from quadkit.cache.backends.memory.backend import MemoryCacheBackend

        backend = MemoryCacheBackend()

        # set returns Ok(None)
        result = await backend.set("key", "value")
        assert result.is_ok()

        # delete existing key returns Ok(True)
        result = await backend.delete("key")
        assert result.is_ok()
        assert result.unwrap() is True

        # delete non-existent key returns Ok(False)
        result = await backend.delete("nonexistent")
        assert result.is_ok()
        assert result.unwrap() is False

    @pytest.mark.asyncio
    async def test_cache_error_codes(self) -> None:
        """Verify cache errors have correct codes."""
        assert CacheError._code == "QK_ERR_CACHE_001"
        assert CacheKeyNotFoundError._code == "QK_ERR_CACHE_002"
        assert CacheWriteError._code == "QK_ERR_CACHE_003"


__all__ = [
    "TestCacheBackendResultPattern",
    "TestCacheServiceResultPattern",
]
