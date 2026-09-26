"""Unit tests for quadkit-cache exceptions.

These tests verify the exception hierarchy and behavior in quadkit.cache.exceptions.
"""

from quadkit.cache import constants as const
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
from quadkit.contracts.exceptions import QuadkitError, SerializationError


class TestCacheExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_cache_error_inherits_from_quadkit_error(self) -> None:
        assert issubclass(CacheError, QuadkitError)

    def test_cache_backend_error_inherits_from_cache_error(self) -> None:
        assert issubclass(CacheBackendError, CacheError)

    def test_cache_connection_error_inherits_from_cache_backend_error(self) -> None:
        assert issubclass(CacheConnectionError, CacheBackendError)

    def test_cache_timeout_error_inherits_from_cache_error(self) -> None:
        assert issubclass(CacheTimeoutError, CacheError)

    def test_cache_key_error_inherits_from_cache_error(self) -> None:
        assert issubclass(CacheKeyError, CacheError)

    def test_cache_configuration_error_inherits_from_cache_error(self) -> None:
        assert issubclass(CacheConfigurationError, CacheError)

    def test_cache_stampede_error_inherits_from_cache_error(self) -> None:
        assert issubclass(CacheStampedeError, CacheError)

    def test_cache_invalidation_error_inherits_from_cache_error(self) -> None:
        assert issubclass(CacheInvalidationError, CacheError)

    def test_lock_acquisition_error_inherits_from_cache_error(self) -> None:
        assert issubclass(LockAcquisitionError, CacheError)

    def test_cache_serialization_error_inherits_from_both(self) -> None:
        assert issubclass(CacheSerializationError, SerializationError)
        assert issubclass(CacheSerializationError, CacheError)

    def test_cache_capacity_error_inherits_from_cache_error(self) -> None:
        assert issubclass(CacheCapacityError, CacheError)


class TestCacheError:
    """Tests for CacheError base exception."""

    def test_cache_error_default_message(self) -> None:
        error = CacheError()
        assert error.message is not None

    def test_cache_error_custom_message(self) -> None:
        error = CacheError(message="Custom error message")
        assert error.message == "Custom error message"


class TestCacheTimeoutError:
    """Tests for CacheTimeoutError."""

    def test_cache_timeout_error_default_message(self) -> None:
        error = CacheTimeoutError()
        assert error.message == const.ERROR_MSG_CACHE_TIMEOUT

    def test_cache_timeout_error_custom_message(self) -> None:
        error = CacheTimeoutError(message="Custom timeout message")
        assert error.message == "Custom timeout message"

    def test_cache_timeout_error_with_key(self) -> None:
        error = CacheTimeoutError(key="test_key")
        # key is accepted as parameter (passed to parent)
        assert error.message is not None

    def test_cache_timeout_error_with_backend(self) -> None:
        error = CacheTimeoutError(backend="redis")
        # backend is accepted as parameter
        assert error.message is not None

    def test_cache_timeout_error_timeout_seconds(self) -> None:
        error = CacheTimeoutError(timeout_seconds=5.0)
        assert error.timeout_seconds == 5.0

    def test_cache_timeout_error_timeout_in_details(self) -> None:
        error = CacheTimeoutError(timeout_seconds=5.0)
        assert error.details.get("timeout_seconds") == 5.0


class TestCacheKeyError:
    """Tests for CacheKeyError."""

    def test_cache_key_error_default_message(self) -> None:
        error = CacheKeyError()
        assert error.message is not None


class TestCacheConfigurationError:
    """Tests for CacheConfigurationError."""

    def test_cache_configuration_error_default_message(self) -> None:
        error = CacheConfigurationError()
        assert error.message == const.ERROR_MSG_CACHE_CONFIGURATION

    def test_cache_configuration_error_custom_message(self) -> None:
        error = CacheConfigurationError(message="Custom config error")
        assert error.message == "Custom config error"

    def test_cache_configuration_error_with_setting(self) -> None:
        error = CacheConfigurationError(setting="redis_host", value="localhost")
        assert error.setting == "redis_host"
        assert error.value == "localhost"

    def test_cache_configuration_error_setting_in_details(self) -> None:
        error = CacheConfigurationError(setting="max_connections", value=100)
        assert error.details.get("setting") == "max_connections"

    def test_cache_configuration_error_value_in_details(self) -> None:
        error = CacheConfigurationError(setting="max_connections", value=100)
        assert "100" in str(error.details.get("value", ""))


class TestCacheStampedeError:
    """Tests for CacheStampedeError."""

    def test_cache_stampede_error_default_message(self) -> None:
        error = CacheStampedeError()
        assert error.message == const.ERROR_MSG_CACHE_STAMPEDE

    def test_cache_stampede_error_custom_message(self) -> None:
        error = CacheStampedeError(message="Custom stampede error")
        assert error.message == "Custom stampede error"

    def test_cache_stampede_error_with_lock_holder(self) -> None:
        error = CacheStampedeError(lock_holder="owner123")
        assert error.lock_holder == "owner123"

    def test_cache_stampede_error_lock_holder_in_details(self) -> None:
        error = CacheStampedeError(lock_holder="owner123")
        assert error.details.get("lock_holder") == "owner123"


class TestCacheInvalidationError:
    """Tests for CacheInvalidationError."""

    def test_cache_invalidation_error_default_message(self) -> None:
        error = CacheInvalidationError()
        assert error.message == const.ERROR_MSG_CACHE_INVALIDATION

    def test_cache_invalidation_error_custom_message(self) -> None:
        error = CacheInvalidationError(message="Custom invalidation error")
        assert error.message == "Custom invalidation error"

    def test_cache_invalidation_error_with_keys(self) -> None:
        error = CacheInvalidationError(keys=["key1", "key2", "key3"])
        assert error.keys == ["key1", "key2", "key3"]

    def test_cache_invalidation_error_with_tag(self) -> None:
        error = CacheInvalidationError(tag="user_123")
        assert error.tag == "user_123"

    def test_cache_invalidation_error_with_pattern(self) -> None:
        error = CacheInvalidationError(pattern="user_*")
        assert error.pattern == "user_*"

    def test_cache_invalidation_error_keys_in_details(self) -> None:
        error = CacheInvalidationError(keys=["key1", "key2", "key3"])
        assert error.details.get("keys") == ["key1", "key2", "key3"]
        assert error.details.get("keys_count") == 3

    def test_cache_invalidation_error_tag_in_details(self) -> None:
        error = CacheInvalidationError(tag="user_123")
        assert error.details.get("tag") == "user_123"


class TestCacheBackendError:
    """Tests for CacheBackendError."""

    def test_cache_backend_error_default_message(self) -> None:
        error = CacheBackendError()
        assert error.message is not None


class TestCacheConnectionError:
    """Tests for CacheConnectionError."""

    def test_cache_connection_error_inheritance(self) -> None:
        error = CacheConnectionError()
        assert isinstance(error, CacheBackendError)
        assert isinstance(error, CacheError)


class TestLockAcquisitionError:
    """Tests for LockAcquisitionError."""

    def test_lock_acquisition_error_default_message(self) -> None:
        error = LockAcquisitionError()
        assert error.message is not None


class TestCacheSerializationError:
    """Tests for CacheSerializationError."""

    def test_cache_serialization_error_inheritance(self) -> None:
        error = CacheSerializationError()
        assert isinstance(error, SerializationError)
        assert isinstance(error, CacheError)


class TestCacheCapacityError:
    """Tests for CacheCapacityError."""

    def test_cache_capacity_error_default_message(self) -> None:
        error = CacheCapacityError()
        assert error.message is not None


class TestExceptionAllExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_all_exceptions(self) -> None:
        expected = [
            "CacheBackendError",
            "CacheCapacityError",
            "CacheConfigurationError",
            "CacheConnectionError",
            "CacheError",
            "CacheInvalidationError",
            "CacheKeyError",
            "CacheSerializationError",
            "CacheStampedeError",
            "CacheTimeoutError",
            "LockAcquisitionError",
        ]
        from quadkit.cache import exceptions as exc_module

        for item in expected:
            assert item in exc_module.__all__
