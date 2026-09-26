"""Tests for cache exceptions."""

import pytest

from quadkit.cache.exceptions import (
    CacheBackendError,
    CacheCapacityError,
    CacheConfigurationError,
    CacheConnectionError,
    CacheError,
    CacheInvalidationError,
    CacheKeyError,
    CacheSerializationError,
    CacheStampedeError,
    CacheTimeoutError,
    LockAcquisitionError,
)


class TestCacheError:
    """Tests for CacheError."""

    def test_cache_error(self) -> None:
        """Test CacheError can be instantiated."""
        err = CacheError("Cache error")
        assert err.message == "Cache error"


class TestCacheBackendError:
    """Tests for CacheBackendError."""

    def test_cache_backend_error(self) -> None:
        """Test CacheBackendError can be instantiated."""
        err = CacheBackendError("Backend failed")
        assert err.message == "Backend failed"


class TestCacheConnectionError:
    """Tests for CacheConnectionError."""

    def test_cache_connection_error(self) -> None:
        """Test CacheConnectionError can be instantiated."""
        err = CacheConnectionError("Connection failed")
        assert err.message == "Connection failed"


class TestCacheTimeoutError:
    """Tests for CacheTimeoutError."""

    def test_cache_timeout_error(self) -> None:
        """Test CacheTimeoutError can be instantiated."""
        err = CacheTimeoutError()
        assert err.message

    def test_cache_timeout_error_with_timeout(self) -> None:
        """Test CacheTimeoutError with timeout value."""
        err = CacheTimeoutError(timeout_seconds=5.0)
        assert err.timeout_seconds == 5.0


class TestCacheKeyError:
    """Tests for CacheKeyError."""

    def test_cache_key_error(self) -> None:
        """Test CacheKeyError can be instantiated."""
        err = CacheKeyError("Invalid key")
        assert err.message == "Invalid key"


class TestCacheConfigurationError:
    """Tests for CacheConfigurationError."""

    def test_cache_configuration_error(self) -> None:
        """Test CacheConfigurationError can be instantiated."""
        err = CacheConfigurationError()
        assert err.message


class TestCacheStampedeError:
    """Tests for CacheStampedeError."""

    def test_cache_stampede_error(self) -> None:
        """Test CacheStampedeError can be instantiated."""
        err = CacheStampedeError("Stampede protection failed")
        assert err.message == "Stampede protection failed"


class TestCacheInvalidationError:
    """Tests for CacheInvalidationError."""

    def test_cache_invalidation_error(self) -> None:
        """Test CacheInvalidationError can be instantiated."""
        err = CacheInvalidationError("Invalidation failed")
        assert err.message == "Invalidation failed"


class TestLockAcquisitionError:
    """Tests for LockAcquisitionError."""

    def test_lock_acquisition_error(self) -> None:
        """Test LockAcquisitionError can be instantiated."""
        err = LockAcquisitionError("Could not acquire lock")
        assert err.message == "Could not acquire lock"


class TestCacheSerializationError:
    """Tests for CacheSerializationError."""

    def test_cache_serialization_error(self) -> None:
        """Test CacheSerializationError can be instantiated."""
        err = CacheSerializationError("Serialization failed")
        assert err.message == "Serialization failed"


class TestCacheCapacityError:
    """Tests for CacheCapacityError."""

    def test_cache_capacity_error(self) -> None:
        """Test CacheCapacityError can be instantiated."""
        err = CacheCapacityError("Cache at capacity")
        assert err.message == "Cache at capacity"
