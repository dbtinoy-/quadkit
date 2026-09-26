"""Unit tests for quadkit.cache.constants module."""

from __future__ import annotations

import pytest

from quadkit.cache import constants


class TestVersion:
    def test_version_defined(self) -> None:
        assert constants.__version__ is not None
        assert isinstance(constants.__version__, str)


class TestEnvPrefixes:
    def test_env_prefix(self) -> None:
        assert constants.ENV_PREFIX == "QK_CACHE__"

    def test_nested_delimiter(self) -> None:
        assert constants.ENV_NESTED_DELIMITER == "__"

    def test_var_quadkit_env(self) -> None:
        assert constants.ENV_VAR_QK_ENV == "QK_ENV"


class TestCacheConfigDefaults:
    def test_default_cache_name(self) -> None:
        assert constants.DEFAULT_CACHE_NAME == "cache"

    def test_default_cache_version(self) -> None:
        assert constants.DEFAULT_CACHE_VERSION == "1.0.0"

    def test_default_cache_enabled(self) -> None:
        assert constants.DEFAULT_CACHE_ENABLED is True

    def test_default_cache_environment(self) -> None:
        assert constants.DEFAULT_CACHE_ENVIRONMENT == "development"

    def test_default_cache_debug(self) -> None:
        assert constants.DEFAULT_CACHE_DEBUG is False


class TestServiceConfigDefaults:
    def test_service_protection_enabled(self) -> None:
        assert constants.DEFAULT_SERVICE_PROTECTION_ENABLED is True

    def test_service_metrics_enabled(self) -> None:
        assert constants.DEFAULT_SERVICE_METRICS_ENABLED is True

    def test_service_health_checks_enabled(self) -> None:
        assert constants.DEFAULT_SERVICE_HEALTH_CHECKS_ENABLED is True

    def test_service_circuit_breaker_enabled(self) -> None:
        assert constants.DEFAULT_SERVICE_CIRCUIT_BREAKER_ENABLED is False

    def test_service_circuit_breaker_threshold(self) -> None:
        assert constants.DEFAULT_SERVICE_CIRCUIT_BREAKER_THRESHOLD == 5

    def test_service_serializer(self) -> None:
        assert constants.DEFAULT_SERVICE_SERIALIZER == "json"


class TestProtectionDefaults:
    def test_protection_lock_ttl(self) -> None:
        assert constants.DEFAULT_PROTECTION_LOCK_TTL == 30

    def test_protection_max_wait(self) -> None:
        assert constants.DEFAULT_PROTECTION_MAX_WAIT == 10.0

    def test_protection_retry_interval(self) -> None:
        assert constants.DEFAULT_PROTECTION_RETRY_INTERVAL == 0.1


class TestMemoryBackendDefaults:
    def test_memory_name(self) -> None:
        assert constants.DEFAULT_MEMORY_NAME == "memory"

    def test_memory_enabled(self) -> None:
        assert constants.DEFAULT_MEMORY_ENABLED is True

    def test_memory_default(self) -> None:
        assert constants.DEFAULT_MEMORY_DEFAULT is False

    def test_memory_cleanup_interval(self) -> None:
        assert constants.DEFAULT_MEMORY_CLEANUP_INTERVAL == 60


class TestRedisBackendDefaults:
    def test_redis_name(self) -> None:
        assert constants.DEFAULT_REDIS_NAME == "redis"

    def test_redis_host(self) -> None:
        assert constants.DEFAULT_REDIS_HOST == "localhost"

    def test_redis_port(self) -> None:
        assert constants.DEFAULT_REDIS_PORT == 6379

    def test_redis_db(self) -> None:
        assert constants.DEFAULT_REDIS_DB == 0

    def test_redis_enabled(self) -> None:
        assert constants.DEFAULT_REDIS_ENABLED is True

    def test_redis_default(self) -> None:
        assert constants.DEFAULT_REDIS_DEFAULT is False

    def test_redis_ssl(self) -> None:
        assert constants.DEFAULT_REDIS_SSL is False

    def test_redis_connection_pool_size(self) -> None:
        assert constants.DEFAULT_REDIS_CONNECTION_POOL_SIZE == 10

    def test_redis_socket_timeout(self) -> None:
        assert constants.DEFAULT_REDIS_SOCKET_TIMEOUT == 5.0

    def test_redis_retry_on_timeout(self) -> None:
        assert constants.DEFAULT_REDIS_RETRY_ON_TIMEOUT is True


class TestMemcachedBackendDefaults:
    def test_memcached_name(self) -> None:
        assert constants.DEFAULT_MEMCACHED_NAME == "memcached"

    def test_memcached_host(self) -> None:
        assert constants.DEFAULT_MEMCACHED_HOST == "localhost"

    def test_memcached_port(self) -> None:
        assert constants.DEFAULT_MEMCACHED_PORT == 11211

    def test_memcached_enabled(self) -> None:
        assert constants.DEFAULT_MEMCACHED_ENABLED is True

    def test_memcached_default(self) -> None:
        assert constants.DEFAULT_MEMCACHED_DEFAULT is False


class TestLockConstants:
    def test_lock_key_prefix(self) -> None:
        assert constants.LOCK_KEY_PREFIX == "lock:"

    def test_default_lock_ttl(self) -> None:
        assert constants.DEFAULT_LOCK_TTL == 30

    def test_lock_renewal_interval_divisor(self) -> None:
        assert constants.DEFAULT_LOCK_RENEWAL_INTERVAL_DIVISOR == 2


class TestCompressionConstants:
    def test_compression_marker_uncompressed(self) -> None:
        assert constants.COMPRESSION_MARKER_UNCOMPRESSED == b"\x00"

    def test_compression_marker_compressed(self) -> None:
        assert constants.COMPRESSION_MARKER_COMPRESSED == b"\x01"

    def test_compression_threshold(self) -> None:
        assert constants.DEFAULT_COMPRESSION_THRESHOLD == 1024

    def test_compression_level(self) -> None:
        assert constants.DEFAULT_COMPRESSION_LEVEL == 6


class TestSecurityConstants:
    def test_insecure_passwords_tuple(self) -> None:
        assert isinstance(constants.INSECURE_PASSWORDS, tuple)
        assert len(constants.INSECURE_PASSWORDS) > 0

    def test_insecure_passwords_contains_known(self) -> None:
        assert "change-me" in constants.INSECURE_PASSWORDS
        assert "password" in constants.INSECURE_PASSWORDS
        assert "123456" in constants.INSECURE_PASSWORDS
        assert "secret" in constants.INSECURE_PASSWORDS


class TestBackendTypeStrings:
    def test_backend_type_memory(self) -> None:
        assert constants.BACKEND_TYPE_MEMORY == "memory"

    def test_backend_type_redis(self) -> None:
        assert constants.BACKEND_TYPE_REDIS == "redis"

    def test_backend_type_memcached(self) -> None:
        assert constants.BACKEND_TYPE_MEMCACHED == "memcached"


class TestCacheStatusStrings:
    def test_cache_status_hit(self) -> None:
        assert constants.CACHE_STATUS_HIT == "hit"

    def test_cache_status_miss(self) -> None:
        assert constants.CACHE_STATUS_MISS == "miss"

    def test_cache_status_set(self) -> None:
        assert constants.CACHE_STATUS_SET == "set"

    def test_cache_status_delete(self) -> None:
        assert constants.CACHE_STATUS_DELETE == "delete"

    def test_cache_status_error(self) -> None:
        assert constants.CACHE_STATUS_ERROR == "error"

    def test_cache_status_expired(self) -> None:
        assert constants.CACHE_STATUS_EXPIRED == "expired"

    def test_cache_status_stale(self) -> None:
        assert constants.CACHE_STATUS_STALE == "stale"


class TestErrorMessages:
    def test_error_msg_cache_timeout(self) -> None:
        assert constants.ERROR_MSG_CACHE_TIMEOUT == "Cache operation timed out"

    def test_error_msg_cache_configuration(self) -> None:
        assert "configuration" in constants.ERROR_MSG_CACHE_CONFIGURATION.lower()

    def test_error_msg_cache_stampede(self) -> None:
        assert "stampede" in constants.ERROR_MSG_CACHE_STAMPEDE.lower()

    def test_error_msg_cache_invalidation(self) -> None:
        assert "invalidation" in constants.ERROR_MSG_CACHE_INVALIDATION.lower()

    def test_error_msg_redis_install(self) -> None:
        assert "redis" in constants.ERROR_MSG_REDIS_INSTALL.lower()

    def test_error_msg_memcached_install(self) -> None:
        assert "memcached" in constants.ERROR_MSG_MEMCACHED_INSTALL.lower()

    def test_error_msg_pyyaml_install(self) -> None:
        assert "pyyaml" in constants.ERROR_MSG_PYYAML_INSTALL.lower()

    def test_error_msg_insecure_password(self) -> None:
        assert "password" in constants.ERROR_MSG_INSECURE_PASSWORD.lower()

    def test_error_msg_insecure_url(self) -> None:
        assert "url" in constants.ERROR_MSG_INSECURE_URL.lower()


class TestFileLoadingConstants:
    def test_default_encoding(self) -> None:
        assert constants.DEFAULT_ENCODING == "utf-8"