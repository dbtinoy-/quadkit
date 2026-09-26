"""Tests for cache integration config module.

Tests the EnvironmentConfigLoader and CacheConfig classes using
the preferred dict-based configuration approach.
"""

from unittest.mock import mock_open, patch

import pytest

from quadkit import serialization as json
from quadkit.cache.config import (
    CacheConfig,
    CacheServiceConfig,
    EnvironmentConfigLoader,
    MemoryBackendConfig,
    RedisBackendConfig,
)
from quadkit.contracts.core.config import Environment


class TestCacheConfig:
    """Test the CacheConfig class."""

    def test_cache_config_defaults(self):
        """Test CacheConfig default values."""
        config = CacheConfig()

        assert config.name == "cache"
        assert config.version == "1.0.0"
        assert config.enabled is True
        assert config.environment == Environment.DEVELOPMENT
        assert config.debug is False
        assert config.backends == []
        assert isinstance(config.service, CacheServiceConfig)

    def test_cache_config_with_backends(self):
        """Test CacheConfig with backend configurations."""
        from quadkit.contracts.core.config import Environment

        config = CacheConfig(
            name="test_config",
            env=Environment.PRODUCTION,
            debug=True,
            backends=[
                MemoryBackendConfig(name="memory_backend", default=True),
                RedisBackendConfig(
                    name="redis_backend",
                    host="redis.example.com",
                    port=6389,
                ),
            ],
            service=CacheServiceConfig(
                enable_protection=False,
                enable_metrics=True,
                default_backend="memory_backend",
            ),
        )

        assert config.name == "test_config"
        assert config.environment == Environment.PRODUCTION
        assert config.debug is True
        assert len(config.backends) == 2
        assert config.backends[0].name == "memory_backend"
        assert config.backends[0].default is True
        assert config.backends[1].name == "redis_backend"
        assert config.backends[1].host == "redis.example.com"
        assert config.service.enable_protection is False
        assert config.service.default_backend == "memory_backend"


class TestEnvironmentConfigLoader:
    """Test the EnvironmentConfigLoader class."""

    def test_from_dict_basic(self):
        """Test loading configuration from a dictionary."""
        from quadkit.contracts.core.config import Environment

        config_dict = {
            "name": "dict_config",
            "env": Environment.TEST,
            "debug": True,
            "backends": [
                {
                    "name": "test_backend",
                    "type": "memory",
                    "default": True,
                    "enabled": True,
                },
            ],
            "service": {
                "enable_protection": False,
                "enable_metrics": True,
            },
        }

        config = EnvironmentConfigLoader.from_dict(config_dict)

        assert isinstance(config, CacheConfig)
        assert config.name == "dict_config"
        assert config.environment == Environment.TEST
        assert config.debug is True
        assert len(config.backends) == 1
        assert config.backends[0].name == "test_backend"
        assert config.service.enable_protection is False
        assert config.service.enable_metrics is True

    def test_from_dict_multiple_backends(self):
        """Test loading configuration with multiple backends."""
        config_dict = {
            "name": "multi_backend_config",
            "backends": [
                {
                    "name": "memory_backend",
                    "type": "memory",
                    "default": False,
                    "enabled": True,
                    "default_ttl": 300,
                    "key_prefix": "mem:",
                },
                {
                    "name": "redis_backend",
                    "type": "redis",
                    "default": True,
                    "enabled": True,
                    "default_ttl": 600,
                    "key_prefix": "redis:",
                    "redis_host": "redis.example.com",
                    "redis_port": 6380,
                    "redis_db": 1,
                    "redis_password": "secret",
                },
            ],
        }

        config = EnvironmentConfigLoader.from_dict(config_dict)

        assert len(config.backends) == 2

        # Memory backend
        mem_backend = config.backends[0]
        assert mem_backend.name == "memory_backend"
        assert mem_backend.type == "memory"
        assert mem_backend.default is False
        assert mem_backend.default_ttl == 300
        assert mem_backend.key_prefix == "mem:"

        # Redis backend
        redis_backend = config.backends[1]
        assert redis_backend.name == "redis_backend"
        assert redis_backend.type == "redis"
        assert redis_backend.default is True
        assert redis_backend.default_ttl == 600
        assert redis_backend.key_prefix == "redis:"
        assert redis_backend.redis_host == "redis.example.com"
        assert redis_backend.redis_port == 6380
        assert redis_backend.redis_db == 1
        assert redis_backend.redis_password == "secret"

    def test_from_dict_memcached_backend(self):
        """Test loading configuration with memcached backend."""
        config_dict = {
            "name": "memcached_config",
            "backends": [
                {
                    "name": "memcached_backend",
                    "type": "memcached",
                    "default": True,
                    "memcached_host": "memcached.example.com",
                    "memcached_port": 11212,
                },
            ],
        }

        config = EnvironmentConfigLoader.from_dict(config_dict)

        assert len(config.backends) == 1
        backend = config.backends[0]
        assert backend.type == "memcached"
        assert backend.default is True
        assert backend.memcached_host == "memcached.example.com"
        assert backend.memcached_port == 11212

    def test_from_json(self):
        """Test loading configuration from JSON file."""
        json_content = {
            "name": "json_config",
            "env": "production",
            "debug": False,
            "backends": [
                {
                    "name": "json_backend",
                    "type": "memcached",
                    "default": True,
                    "enabled": True,
                    "memcached_host": "memcached.prod.com",
                    "memcached_port": 11211,
                },
            ],
            "service": {
                "enable_protection": False,
                "enable_metrics": True,
                "default_backend": "json_backend",
            },
        }

        with patch("builtins.open", mock_open(read_data=json.dumps(json_content))):
            config = EnvironmentConfigLoader.from_json("test.json")

            assert config.name == "json_config"
            assert config.environment == "production"
            assert config.debug is False
            assert len(config.backends) == 1
            assert config.backends[0].name == "json_backend"
            assert config.service.enable_protection is False
            assert config.service.default_backend == "json_backend"

    def test_from_yaml(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
name: yaml_config
environment: staging
debug: false
backends:
  - name: yaml_backend
    type: redis
    default: true
    enabled: true
    redis_host: redis.staging.com
    redis_port: 6379
service:
  enable_protection: true
  enable_metrics: false
"""

        with patch("builtins.open", mock_open(read_data=yaml_content)):
            with patch("yaml.safe_load") as mock_yaml:
                mock_yaml.return_value = {
                    "name": "yaml_config",
                    "env": "staging",
                    "debug": False,
                    "backends": [
                        {
                            "name": "yaml_backend",
                            "type": "redis",
                            "default": True,
                            "enabled": True,
                            "redis_host": "redis.staging.com",
                            "redis_port": 6379,
                        },
                    ],
                    "service": {
                        "enable_protection": True,
                        "enable_metrics": False,
                    },
                }

                config = EnvironmentConfigLoader.from_yaml("test.yaml")

                assert config.name == "yaml_config"
                assert config.environment == "staging"
                assert config.debug is False
                assert len(config.backends) == 1
                assert config.backends[0].name == "yaml_backend"
                assert config.service.enable_protection is True

    def test_from_yaml_missing_pyyaml(self):
        """Test YAML loading when PyYAML is not available."""
        with patch.dict("sys.modules", {"yaml": None}):
            with pytest.raises(
                ImportError, match="PyYAML is required for YAML configuration loading",
            ):
                EnvironmentConfigLoader.from_yaml("test.yaml")

    def test_from_dict_ttl_zero_becomes_none(self):
        """Test that TTL of 0 is preserved (not converted to None)."""
        config_dict = {
            "name": "ttl_test",
            "backends": [
                {
                    "name": "test_backend",
                    "type": "memory",
                    "default": True,
                    "default_ttl": 0,
                },
            ],
        }

        config = EnvironmentConfigLoader.from_dict(config_dict)

        assert config.backends[0].default_ttl == 0

    def test_from_dict_empty_backends(self):
        """Test loading configuration with empty backends list."""
        config_dict = {
            "name": "empty_config",
            "backends": [],
        }

        config = EnvironmentConfigLoader.from_dict(config_dict)

        assert config.name == "empty_config"
        assert len(config.backends) == 0

    def test_from_dict_no_backends_key(self):
        """Test loading configuration without backends key."""
        config_dict = {
            "name": "no_backends_config",
            "env": "test",
        }

        config = EnvironmentConfigLoader.from_dict(config_dict)

        assert config.name == "no_backends_config"
        assert config.environment == "test"
        assert len(config.backends) == 0
