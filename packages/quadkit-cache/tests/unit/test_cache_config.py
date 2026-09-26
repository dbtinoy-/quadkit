"""Unit tests for quadkit-cache configuration.

Tests verify the configuration classes and helpers in quadkit.cache.config.
"""

import pytest
from quadkit.cache import constants as const
from quadkit.cache.config import (
    BACKEND_TYPE_MAP,
    CacheBackendConfig,
    CacheConfig,
    CacheOperationConfig,
    CacheServiceConfig,
    EnvironmentConfigLoader,
    MemcachedBackendConfig,
    MemoryBackendConfig,
    RedisBackendConfig,
    default_cache_config,
    get_backend_type_from_string,
    make_cache_config,
    make_cache_service_config,
)
from quadkit.cache.types import BackendType
from quadkit.contracts.core.config import Environment


class TestCacheOperationConfig:
    """Tests for CacheOperationConfig."""

    def test_default_values(self) -> None:
        config = CacheOperationConfig()
        assert config.default_ttl is None
        assert config.max_memory is None
        assert config.key_prefix == ""
        assert config.enable_metrics is True
        assert config.serializer_type == const.DEFAULT_SERVICE_SERIALIZER

    def test_custom_values(self) -> None:
        config = CacheOperationConfig(
            default_ttl=300,
            max_memory=1024,
            key_prefix="test",
            enable_metrics=False,
            serializer_type="msgpack",
        )
        assert config.default_ttl == 300
        assert config.max_memory == 1024
        assert config.key_prefix == "test"
        assert config.enable_metrics is False
        assert config.serializer_type == "msgpack"

    def test_make_key_with_prefix(self) -> None:
        config = CacheOperationConfig(key_prefix="app")
        key = config.make_key("user:1")
        assert key == "app:user:1"

    def test_make_key_without_prefix(self) -> None:
        config = CacheOperationConfig()
        key = config.make_key("user:1")
        assert key == "user:1"

    def test_strip_prefix(self) -> None:
        config = CacheOperationConfig(key_prefix="app")
        key = config.strip_prefix("app:user:1")
        assert key == "user:1"

    def test_strip_prefix_no_match(self) -> None:
        config = CacheOperationConfig(key_prefix="app")
        key = config.strip_prefix("other:user:1")
        assert key == "other:user:1"


class TestMemoryBackendConfig:
    """Tests for MemoryBackendConfig."""

    def test_default_values(self) -> None:
        config = MemoryBackendConfig()
        assert config.name == const.DEFAULT_MEMORY_NAME
        assert config.default is const.DEFAULT_MEMORY_DEFAULT
        assert config.enabled is const.DEFAULT_MEMORY_ENABLED
        assert config.default_ttl is None
        assert config.max_size is None
        assert config.cleanup_interval == const.DEFAULT_MEMORY_CLEANUP_INTERVAL
        assert config.key_prefix == ""
        assert config.backend_type == BackendType.MEMORY


class TestRedisBackendConfig:
    """Tests for RedisBackendConfig."""

    def test_default_values(self) -> None:
        config = RedisBackendConfig()
        assert config.name == const.DEFAULT_REDIS_NAME
        assert config.default is const.DEFAULT_REDIS_DEFAULT
        assert config.enabled is const.DEFAULT_REDIS_ENABLED
        assert config.host == const.DEFAULT_REDIS_HOST
        assert config.port == const.DEFAULT_REDIS_PORT
        assert config.db == const.DEFAULT_REDIS_DB
        assert config.password is None
        assert config.url is None
        assert config.ssl is const.DEFAULT_REDIS_SSL
        assert config.backend_type == BackendType.REDIS

    def test_redis_url_no_auth(self) -> None:
        config = RedisBackendConfig(host="localhost", port=6379, db=0)
        assert config.redis_url == "redis://localhost:6379/0"

    def test_redis_url_with_ssl(self) -> None:
        config = RedisBackendConfig(host="localhost", port=6379, db=0, ssl=True)
        assert config.redis_url == "rediss://localhost:6379/0"

    def test_redis_url_with_password(self) -> None:
        config = RedisBackendConfig(
            host="localhost", port=6379, db=0, password="secret"
        )
        assert config.redis_url == "redis://:secret@localhost:6379/0"

    def test_redis_url_with_url_override(self) -> None:
        config = RedisBackendConfig(url="redis://custom:6390/5")
        assert config.redis_url == "redis://custom:6390/5"

    def test_custom_config(self) -> None:
        config = RedisBackendConfig(
            name="my-redis",
            default=True,
            host="redis.example.com",
            port=6380,
            db=1,
            password="pass123",
            key_prefix="cache",
        )
        assert config.name == "my-redis"
        assert config.default is True
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 1
        assert config.password == "pass123"
        assert config.key_prefix == "cache"


class TestMemcachedBackendConfig:
    """Tests for MemcachedBackendConfig."""

    def test_default_values(self) -> None:
        config = MemcachedBackendConfig()
        assert config.name == const.DEFAULT_MEMCACHED_NAME
        assert config.default is const.DEFAULT_MEMCACHED_DEFAULT
        assert config.enabled is const.DEFAULT_MEMCACHED_ENABLED
        assert config.host == const.DEFAULT_MEMCACHED_HOST
        assert config.port == const.DEFAULT_MEMCACHED_PORT
        assert config.servers is None
        assert config.backend_type == BackendType.MEMCACHED

    def test_server_list_default(self) -> None:
        config = MemcachedBackendConfig()
        assert config.server_list == [f"{const.DEFAULT_MEMCACHED_HOST}:{const.DEFAULT_MEMCACHED_PORT}"]

    def test_server_list_custom_servers(self) -> None:
        config = MemcachedBackendConfig(
            servers=["server1:11211", "server2:11211"]
        )
        assert config.server_list == ["server1:11211", "server2:11211"]


class TestCacheBackendConfig:
    """Tests for unified CacheBackendConfig."""

    def test_memory_backend(self) -> None:
        config = CacheBackendConfig(
            name="memory",
            type=BackendType.MEMORY,
            default=True,
            enabled=True,
        )
        assert config.name == "memory"
        assert config.type == BackendType.MEMORY
        assert config.default is True
        assert config.enabled is True

    def test_redis_backend_builds_url(self) -> None:
        config = CacheBackendConfig(
            name="redis",
            type=BackendType.REDIS,
            default=True,
            redis_host="localhost",
            redis_port=6379,
            redis_db=0,
            redis_password="secret",
            redis_ssl=True,
        )
        assert config.redis_url == "rediss://:secret@localhost:6379/0"

    def test_memcached_backend_builds_servers(self) -> None:
        config = CacheBackendConfig(
            name="memcached",
            type=BackendType.MEMCACHED,
            default=True,
            memcached_host="localhost",
            memcached_port=11211,
        )
        assert config.memcached_servers == ["localhost:11211"]


class TestCacheServiceConfig:
    """Tests for CacheServiceConfig."""

    def test_default_values(self) -> None:
        config = CacheServiceConfig()
        assert config.enable_protection is const.DEFAULT_SERVICE_PROTECTION_ENABLED
        assert config.enable_metrics is const.DEFAULT_SERVICE_METRICS_ENABLED
        assert config.enable_health_checks is const.DEFAULT_SERVICE_HEALTH_CHECKS_ENABLED
        assert config.protection_lock_ttl == const.DEFAULT_PROTECTION_LOCK_TTL
        assert config.protection_max_wait == const.DEFAULT_PROTECTION_MAX_WAIT
        assert config.protection_retry_interval == const.DEFAULT_PROTECTION_RETRY_INTERVAL
        assert config.default_backend is None
        assert config.circuit_breaker_enabled is const.DEFAULT_SERVICE_CIRCUIT_BREAKER_ENABLED
        assert config.circuit_breaker_threshold == const.DEFAULT_SERVICE_CIRCUIT_BREAKER_THRESHOLD
        assert config.default_serializer == const.DEFAULT_SERVICE_SERIALIZER

    def test_custom_values(self) -> None:
        config = CacheServiceConfig(
            enable_protection=False,
            enable_metrics=False,
            enable_health_checks=False,
            protection_lock_ttl=60,
            protection_max_wait=10.0,
            protection_retry_interval=0.5,
            default_backend="redis",
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=100,
            default_serializer="json",
        )
        assert config.enable_protection is False
        assert config.enable_metrics is False
        assert config.enable_health_checks is False
        assert config.protection_lock_ttl == 60
        assert config.protection_max_wait == 10.0
        assert config.protection_retry_interval == 0.5
        assert config.default_backend == "redis"
        assert config.circuit_breaker_enabled is True
        assert config.circuit_breaker_threshold == 100
        assert config.default_serializer == "json"


class TestCacheConfig:
    """Tests for top-level CacheConfig."""

    def test_default_values(self) -> None:
        config = CacheConfig()
        assert config.name == const.DEFAULT_CACHE_NAME
        assert config.version == const.DEFAULT_CACHE_VERSION
        assert config.enabled is const.DEFAULT_CACHE_ENABLED
        assert config.backends == []
        assert config.service == CacheServiceConfig()
        assert config.environment == const.DEFAULT_CACHE_ENVIRONMENT
        assert config.debug is const.DEFAULT_CACHE_DEBUG

    def test_with_backends(self) -> None:
        backends = [
            CacheBackendConfig(name="memory", type=BackendType.MEMORY, default=True),
            CacheBackendConfig(name="redis", type=BackendType.REDIS, default=False),
        ]
        config = CacheConfig(backends=backends)
        assert len(config.backends) == 2
        assert config.get_default_backend().name == "memory"
        assert config.get_backend("redis").name == "redis"
        assert config.get_backend("nonexistent") is None

    def test_default_backend_first(self) -> None:
        backends = [
            CacheBackendConfig(name="memory", type=BackendType.MEMORY, default=True),
        ]
        config = CacheConfig(backends=backends)
        assert config.get_default_backend().name == "memory"

    def test_validate_unique_names(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            CacheConfig(
                backends=[
                    CacheBackendConfig(name="same", type=BackendType.MEMORY, default=True),
                    CacheBackendConfig(name="same", type=BackendType.REDIS, default=False),
                ]
            )

    def test_validate_one_default(self) -> None:
        with pytest.raises(ValueError, match="one backend must be marked as default"):
            CacheConfig(
                backends=[
                    CacheBackendConfig(name="a", type=BackendType.MEMORY, default=False),
                    CacheBackendConfig(name="b", type=BackendType.REDIS, default=False),
                ]
            )

    def test_production_blocks_insecure_redis_password(self) -> None:
        with pytest.raises(ValueError, match="Insecure Redis password"):
            CacheConfig(
                env=Environment.PRODUCTION,
                backends=[
                    CacheBackendConfig(
                        name="redis",
                        type=BackendType.REDIS,
                        default=True,
                        redis_password="change-me",
                    ),
                ],
            )

    def test_production_blocks_insecure_redis_url(self) -> None:
        with pytest.raises(ValueError, match="Insecure Redis URL"):
            CacheConfig(
                env=Environment.PRODUCTION,
                backends=[
                    CacheBackendConfig(
                        name="redis",
                        type=BackendType.REDIS,
                        default=True,
                        redis_url="redis://:password@localhost:6379/0",
                    ),
                ],
            )

    def test_production_accepts_secure_redis(self) -> None:
        config = CacheConfig(
            env=Environment.PRODUCTION,
            backends=[
                CacheBackendConfig(
                    name="redis",
                    type=BackendType.REDIS,
                    default=True,
                    redis_password="strong-secret",
                ),
            ],
        )
        assert config.environment == Environment.PRODUCTION

    def test_non_production_allows_insecure_redis(self) -> None:
        config = CacheConfig(
            env=Environment.DEVELOPMENT,
            backends=[
                CacheBackendConfig(
                    name="redis",
                    type=BackendType.REDIS,
                    default=True,
                    redis_password="password",
                ),
            ],
        )
        assert config.environment == Environment.DEVELOPMENT


class TestBackendTypeMap:
    """Tests for backend type helpers."""

    def test_backend_type_map_values(self) -> None:
        assert BACKEND_TYPE_MAP["memory"] == BackendType.MEMORY
        assert BACKEND_TYPE_MAP["redis"] == BackendType.REDIS
        assert BACKEND_TYPE_MAP["memcached"] == BackendType.MEMCACHED

    def test_get_backend_type_from_string(self) -> None:
        assert get_backend_type_from_string("memory") == BackendType.MEMORY
        assert get_backend_type_from_string("redis") == BackendType.REDIS
        assert get_backend_type_from_string("memcached") == BackendType.MEMCACHED

    def test_get_backend_type_unknown_defaults_to_memory(self) -> None:
        assert get_backend_type_from_string("unknown") == BackendType.MEMORY


class TestHelperFunctions:
    """Tests for helper factory functions."""

    def test_default_cache_config(self) -> None:
        config = default_cache_config()
        assert isinstance(config, CacheOperationConfig)
        assert config.key_prefix == ""
        assert config.enable_metrics is True

    def test_make_cache_config(self) -> None:
        config = make_cache_config(
            name="test",
            enabled=True,
            backends=[],
        )
        assert config.name == "test"
        assert config.enabled is True
        assert config.backends == []

    def test_make_cache_service_config(self) -> None:
        config = make_cache_service_config(
            enable_protection=False,
            enable_metrics=False,
        )
        assert config.enable_protection is False
        assert config.enable_metrics is False


class TestEnvironmentConfigLoader:
    """Tests for EnvironmentConfigLoader."""

    def test_from_dict(self) -> None:
        config_dict = {
            "name": "test-cache",
            "enabled": True,
            "backends": [
                {"name": "test", "type": "memory", "default": True}
            ],
        }
        config = EnvironmentConfigLoader.from_dict(config_dict)
        assert config.name == "test-cache"
        assert config.enabled is True
        assert len(config.backends) == 1

    def test_from_json_file(self, tmp_path) -> None:
        import json

        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "name": "json-cache",
                    "enabled": True,
                    "backends": [
                        {"name": "test", "type": "memory", "default": True}
                    ],
                }
            )
        )
        config = EnvironmentConfigLoader.from_json(str(config_file))
        assert config.name == "json-cache"
        assert config.enabled is True

    def test_from_yaml_file(self, tmp_path) -> None:
        try:
            import yaml
        except ImportError:
            pytest.skip("pyyaml not installed")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("name: yaml-cache\nenabled: true\nbackends: []\n")

        config = EnvironmentConfigLoader.from_yaml(str(config_file))
        assert config.name == "yaml-cache"
        assert config.enabled is True