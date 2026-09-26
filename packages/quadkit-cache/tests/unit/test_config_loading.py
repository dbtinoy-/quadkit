"""Unit tests for cache configuration and loading."""

from __future__ import annotations

from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from quadkit import serialization as serial
from quadkit.cache import constants as const
from quadkit.cache.config import (
    CacheConfig,
    CacheOperationConfig,
    CacheServiceConfig,
    EnvironmentConfigLoader,
    MemoryBackendConfig,
    RedisBackendConfig,
    default_cache_config,
    get_backend_type_from_string,
    make_cache_config,
    make_cache_service_config,
)
from quadkit.cache.types import BackendType


class TestCacheConfig:
    """Test suite for CacheConfig."""

    def test_default_values(self):
        """Test CacheConfig has correct default values."""
        config = CacheConfig()

        assert config.name == const.DEFAULT_CACHE_NAME
        assert config.version == const.DEFAULT_CACHE_VERSION
        assert config.enabled == const.DEFAULT_CACHE_ENABLED
        assert config.environment == const.DEFAULT_CACHE_ENVIRONMENT
        assert config.debug is False
        assert config.backends == []
        assert isinstance(config.service, CacheServiceConfig)

    def test_custom_values(self):
        """Test CacheConfig accepts custom values."""
        from quadkit.contracts.core.config import Environment

        config = CacheConfig(
            name="test_cache",
            version="1.0",
            enabled=True,
            env=Environment.TEST,
            debug=True,
        )

        assert config.name == "test_cache"
        assert config.version == "1.0"
        assert config.enabled is True
        assert config.environment == Environment.TEST
        assert config.debug is True

    def test_with_backends(self):
        """Test CacheConfig with backend configurations."""
        backend = MemoryBackendConfig(name="default", type=BackendType.MEMORY, default=True)
        config = CacheConfig(backends=[backend])

        assert len(config.backends) == 1
        assert config.backends[0].name == "default"

    def test_get_default_backend(self):
        """Test get_default_backend returns correct backend."""
        backend = MemoryBackendConfig(name="default", type=BackendType.MEMORY, default=True)
        config = CacheConfig(backends=[backend])

        default = config.get_default_backend()
        assert default is not None
        assert default.name == "default"

    def test_get_backend_by_name(self):
        """Test get_backend returns correct backend by name."""
        backend1 = MemoryBackendConfig(name="local", default=True)
        backend2 = RedisBackendConfig(name="redis")
        config = CacheConfig(backends=[backend1, backend2])

        found = config.get_backend("redis")
        assert found is not None
        assert found.name == "redis"

    def test_get_backend_not_found(self):
        """Test get_backend returns None for unknown name."""
        config = CacheConfig(backends=[])
        assert config.get_backend("nonexistent") is None

    def test_validation_rejects_duplicate_backend_names(self):
        """Test validation rejects duplicate backend names."""
        backend1 = MemoryBackendConfig(name="test", default=True)
        backend2 = MemoryBackendConfig(name="test")

        with pytest.raises(ValueError, match="Backend names must be unique"):
            CacheConfig(backends=[backend1, backend2])

    def test_validation_rejects_multiple_default_backends(self):
        """Test validation rejects multiple default backends."""
        backend1 = MemoryBackendConfig(name="default1", type=BackendType.MEMORY, default=True)
        backend2 = MemoryBackendConfig(name="default2", type=BackendType.MEMORY, default=True)

        with pytest.raises(ValueError, match="Exactly one backend must be marked as default"):
            CacheConfig(backends=[backend1, backend2])

    def test_get_provider_class(self):
        """Test get_provider_class returns CacheProvider."""
        from quadkit.cache import CacheProvider

        config = CacheConfig()
        provider_cls = config.get_provider_class()
        assert provider_cls is CacheProvider


class TestCacheServiceConfig:
    """Test suite for CacheServiceConfig."""

    def test_default_values(self):
        """Test CacheServiceConfig has correct defaults."""
        config = CacheServiceConfig()

        assert config.enable_protection is True
        assert config.enable_metrics is True
        assert config.enable_health_checks is True
        assert config.default_backend is None
        assert config.circuit_breaker_enabled is False
        assert config.default_serializer == "json"

    def test_custom_values(self):
        """Test CacheServiceConfig accepts custom values."""
        config = CacheServiceConfig(
            enable_protection=False,
            enable_metrics=False,
            default_backend="redis",
        )

        assert config.enable_protection is False
        assert config.enable_metrics is False
        assert config.default_backend == "redis"


class TestCacheOperationConfig:
    """Test suite for CacheOperationConfig."""

    def test_default_values(self):
        """Test CacheOperationConfig has correct defaults."""
        config = CacheOperationConfig()

        assert config.default_ttl is None
        assert config.max_memory is None
        assert config.key_prefix == ""
        assert config.enable_metrics is True
        assert config.serializer_type == "json"

    def test_make_key_with_prefix(self):
        """Test make_key adds prefix."""
        config = CacheOperationConfig(key_prefix="app")
        key = config.make_key("user:1")

        assert key == "app:user:1"

    def test_make_key_without_prefix(self):
        """Test make_key returns key as-is when no prefix."""
        config = CacheOperationConfig(key_prefix="")
        key = config.make_key("user:1")

        assert key == "user:1"

    def test_strip_prefix(self):
        """Test strip_prefix removes prefix."""
        config = CacheOperationConfig(key_prefix="app")
        key = config.strip_prefix("app:user:1")

        assert key == "user:1"

    def test_strip_prefix_no_match(self):
        """Test strip_prefix returns original when no match."""
        config = CacheOperationConfig(key_prefix="app")
        key = config.strip_prefix("other:user:1")

        assert key == "other:user:1"


class TestConfigLoader:
    """Test suite for EnvironmentConfigLoader."""

    def test_from_dict(self):
        """Test loading config from dictionary."""
        config_dict = {
            "name": "test_cache",
            "enabled": True,
            "backends": [
                {"name": "default", "type": "memory", "default": True}
            ],
        }

        config = EnvironmentConfigLoader.from_dict(config_dict)

        assert config.name == "test_cache"
        assert config.enabled is True
        assert len(config.backends) == 1
        assert config.backends[0].name == "default"

    def test_from_dict_with_service(self):
        """Test loading config from dict with service settings."""
        config_dict = {
            "name": "test_cache",
            "backends": [
                {"name": "default", "type": "memory", "default": True}
            ],
            "service": {
                "enable_protection": False,
                "default_backend": "memory",
            },
        }

        config = EnvironmentConfigLoader.from_dict(config_dict)

        assert config.service.enable_protection is False
        assert config.service.default_backend == "memory"

    def test_from_json_file(self):
        """Test loading config from JSON file."""
        config_dict = {
            "name": "json_cache",
            "backends": [
                {"name": "default", "type": "memory", "default": True}
            ],
        }

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
            f.write(serial.dumps(config_dict))
            temp_path = f.name

        try:
            config = EnvironmentConfigLoader.from_json(temp_path)
            assert config.name == "json_cache"
            assert len(config.backends) == 1
        finally:
            Path(temp_path).unlink()

    def test_from_yaml_file_not_installed(self):
        """Test from_yaml raises ImportError when PyYAML not installed."""
        with patch.dict("sys.modules", {"yaml": None}):
            with pytest.raises(ImportError, match="PyYAML"):
                EnvironmentConfigLoader.from_yaml("nonexistent.yaml")

    def test_from_yaml_file_not_found(self):
        """Test from_yaml raises error for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            EnvironmentConfigLoader.from_yaml("/nonexistent/config.yaml")

    def test_from_env_no_vars(self):
        """Test from_env returns default config when no env vars."""
        with patch.dict("os.environ", {}, clear=True):
            config = EnvironmentConfigLoader.from_env("NONEXISTENT_PREFIX")
            assert config.name == const.DEFAULT_CACHE_NAME


class TestConfigFactories:
    """Test suite for config factory functions."""

    def test_default_cache_config(self):
        """Test default_cache_config returns correct defaults."""
        config = default_cache_config()

        assert isinstance(config, CacheOperationConfig)
        assert config.default_ttl is None
        assert config.max_memory is None
        assert config.key_prefix == ""
        assert config.enable_metrics is True
        assert config.serializer_type == "json"

    def test_make_cache_config(self):
        """Test make_cache_config creates config from kwargs."""
        config = make_cache_config(
            name="factory_cache",
            enabled=True,
            backends=[{"name": "default", "type": "memory", "default": True}],
        )

        assert config.name == "factory_cache"
        assert config.enabled is True

    def test_make_cache_service_config(self):
        """Test make_cache_service_config creates config from kwargs."""
        config = make_cache_service_config(
            enable_protection=False,
            default_backend="redis",
        )

        assert config.enable_protection is False
        assert config.default_backend == "redis"


class TestBackendTypeMapping:
    """Test suite for backend type mapping."""

    @pytest.mark.parametrize(
        ("type_str", "expected"),
        [
            ("memory", BackendType.MEMORY),
            ("Memory", BackendType.MEMORY),
            ("MEMORY", BackendType.MEMORY),
            ("redis", BackendType.REDIS),
            ("Redis", BackendType.REDIS),
            ("memcached", BackendType.MEMCACHED),
            ("Memcached", BackendType.MEMCACHED),
            ("unknown", BackendType.MEMORY),
            ("", BackendType.MEMORY),
        ],
    )
    def test_get_backend_type_from_string(self, type_str: str, expected: BackendType):
        """Test backend type string mapping."""
        result = get_backend_type_from_string(type_str)
        assert result == expected


class TestMemoryBackendConfig:
    """Test suite for MemoryBackendConfig."""

    def test_defaults(self):
        """Test MemoryBackendConfig default values."""
        config = MemoryBackendConfig()

        assert config.name == "memory"
        assert config.default is False
        assert config.enabled is True

    def test_custom_values(self):
        """Test MemoryBackendConfig accepts custom values."""
        config = MemoryBackendConfig(
            name="local",
            default=True,
            max_memory=1024 * 1024 * 100,
        )

        assert config.name == "local"
        assert config.default is True
        assert config.max_memory == 1024 * 1024 * 100


class TestRedisBackendConfig:
    """Test suite for RedisBackendConfig."""

    def test_defaults(self):
        """Test RedisBackendConfig default values."""
        config = RedisBackendConfig()

        assert config.name == "redis"
        assert config.default is False
        assert config.enabled is True

    def test_with_url(self):
        """Test RedisBackendConfig with url."""
        config = RedisBackendConfig(
            name="cache",
            url="redis://localhost:6379/0",
        )

        assert config.url == "redis://localhost:6379/0"

    def test_with_password(self):
        """Test RedisBackendConfig with password."""
        config = RedisBackendConfig(
            name="secure_cache",
            password="secret",
        )

        assert config.password == "secret"
