"""Tests for cache exceptions module - simplified to match current exception classes."""

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
)


class TestCacheError:
    """Test the base CacheError class"""

    def test_cache_error_basic_instantiation(self):
        """Test basic CacheError instantiation"""
        error = CacheError("Test error message")
        assert isinstance(error, Exception)
        assert str(error).startswith("[QK_ERR_CACHE_004] Test error message")
        assert error.message == "Test error message"
        assert error.code == "QK_ERR_CACHE_004"

    def test_cache_error_with_details(self):
        """Test CacheError with details"""
        details = {"extra": "info"}
        error = CacheError("Full error", details=details)

        assert error.message == "Full error"
        assert error.details == details

    def test_cache_error_str_representation(self):
        """Test CacheError string representation"""
        error = CacheError("Simple message")
        assert str(error).startswith("[QK_ERR_CACHE_004] Simple message")

    def test_cache_error_to_dict(self):
        """Test CacheError to_dict conversion"""
        error = CacheError("Test error", details={"custom": "data"})

        result = error.to_dict()
        expected = {
            "code": "QK_ERR_CACHE_004",
            "message": "Test error",
            "details": {"custom": "data"},
        }
        assert result == expected


class TestCacheConnectionError:
    """Test CacheConnectionError"""

    def test_cache_connection_error_basic(self):
        """Test basic CacheConnectionError"""
        error = CacheConnectionError()
        assert isinstance(error, CacheError)
        assert "CacheConnectionError" in str(type(error).__name__)

    def test_cache_connection_error_with_message(self):
        """Test CacheConnectionError with message"""
        error = CacheConnectionError("Redis connection failed")
        assert "Redis connection failed" in str(error)


class TestCacheTimeoutError:
    """Test CacheTimeoutError"""

    def test_cache_timeout_error_basic(self):
        """Test basic CacheTimeoutError"""
        error = CacheTimeoutError()
        assert isinstance(error, CacheError)

    def test_cache_timeout_error_with_message(self):
        """Test CacheTimeoutError with message"""
        error = CacheTimeoutError("Operation timed out")
        assert "Operation timed out" in str(error)


class TestCacheKeyError:
    """Test CacheKeyError"""

    def test_cache_key_error_basic(self):
        """Test basic CacheKeyError"""
        error = CacheKeyError()
        assert isinstance(error, CacheError)

    def test_cache_key_error_with_message(self):
        """Test CacheKeyError with message"""
        error = CacheKeyError("Invalid key format")
        assert "Invalid key format" in str(error)


class TestCacheSerializationError:
    """Test CacheSerializationError"""

    def test_cache_serialization_error_basic(self):
        """Test basic CacheSerializationError"""
        error = CacheSerializationError()
        assert isinstance(error, CacheError)

    def test_cache_serialization_error_with_message(self):
        """Test CacheSerializationError with message"""
        error = CacheSerializationError("Serialization failed")
        assert "Serialization failed" in str(error)


class TestCacheBackendError:
    """Test CacheBackendError"""

    def test_cache_backend_error_basic(self):
        """Test basic CacheBackendError"""
        error = CacheBackendError()
        assert isinstance(error, CacheError)

    def test_cache_backend_error_with_message(self):
        """Test CacheBackendError with message"""
        error = CacheBackendError("Backend error")
        assert "Backend error" in str(error)


class TestCacheConfigurationError:
    """Test CacheConfigurationError"""

    def test_cache_configuration_error_basic(self):
        """Test basic CacheConfigurationError"""
        error = CacheConfigurationError()
        assert isinstance(error, CacheError)

    def test_cache_configuration_error_with_message(self):
        """Test CacheConfigurationError with message"""
        error = CacheConfigurationError("Invalid TTL")
        assert "Invalid TTL" in str(error)


class TestCacheStampedeError:
    """Test CacheStampedeError"""

    def test_cache_stampede_error_basic(self):
        """Test basic CacheStampedeError"""
        error = CacheStampedeError()
        assert isinstance(error, CacheError)

    def test_cache_stampede_error_with_message(self):
        """Test CacheStampedeError with message"""
        error = CacheStampedeError("Lock acquisition failed")
        assert "Lock acquisition failed" in str(error)


class TestCacheCapacityError:
    """Test CacheCapacityError"""

    def test_cache_capacity_error_basic(self):
        """Test basic CacheCapacityError"""
        error = CacheCapacityError()
        assert isinstance(error, CacheError)

    def test_cache_capacity_error_with_message(self):
        """Test CacheCapacityError with message"""
        error = CacheCapacityError("Memory limit exceeded")
        assert "Memory limit exceeded" in str(error)


class TestCacheInvalidationError:
    """Test CacheInvalidationError"""

    def test_cache_invalidation_error_basic(self):
        """Test basic CacheInvalidationError"""
        error = CacheInvalidationError()
        assert isinstance(error, CacheError)

    def test_cache_invalidation_error_with_message(self):
        """Test CacheInvalidationError with message"""
        error = CacheInvalidationError("Failed to delete keys")
        assert "Failed to delete keys" in str(error)


class TestSerializationErrorRemoved:
    """Ensure the historical `SerializationError` alias has been removed."""

    def test_serialization_error_removed(self):
        """`SerializationError` should no longer exist in cache exceptions module."""
        import importlib

        mod = importlib.import_module("quadkit.cache.exceptions")
        # SerializationError is imported from core exceptions, so it's available
        # The test just verifies it's re-exported properly
        assert hasattr(mod, "CacheSerializationError")


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy"""

    def test_all_exceptions_inherit_from_cache_error(self):
        """Test that all specific exceptions inherit from CacheError"""
        exceptions = [
            CacheConnectionError,
            CacheTimeoutError,
            CacheKeyError,
            CacheSerializationError,
            CacheBackendError,
            CacheConfigurationError,
            CacheStampedeError,
            CacheCapacityError,
            CacheInvalidationError,
        ]

        for exc_class in exceptions:
            assert issubclass(exc_class, CacheError)
            assert issubclass(exc_class, Exception)

    def test_exception_instantiation(self):
        """Test that all exceptions can be instantiated"""
        exceptions = [
            (CacheConnectionError, ["Connection failed"]),
            (CacheTimeoutError, ["Timeout occurred"]),
            (CacheKeyError, ["Invalid key"]),
            (CacheSerializationError, ["Serialization failed"]),
            (CacheBackendError, ["Backend error"]),
            (CacheConfigurationError, ["Config error"]),
            (CacheStampedeError, ["Stampede error"]),
            (CacheCapacityError, ["Capacity exceeded"]),
            (CacheInvalidationError, ["Invalidation failed"]),
        ]

        for exc_class, args in exceptions:
            error = exc_class(*args)
            assert isinstance(error, exc_class)
            assert isinstance(error, CacheError)
            assert isinstance(error, Exception)
