"""Tests for cache module."""

from __future__ import annotations

import pytest

from quadkit.cache import CacheModule
from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
from quadkit.di.module import DynamicModule


class TestCacheModule:
    """Test suite for CacheModule."""

    def test_module_decorator_exists(self) -> None:
        """Verify @module decorator is applied to CacheModule."""
        assert hasattr(CacheModule, '__quadkit_module__')

    def test_configure_with_none(self) -> None:
        """Verify configure() with None returns DynamicModule."""
        result = CacheModule.configure(None)
        assert isinstance(result, DynamicModule)
        assert result.module is CacheModule

    def test_configure_with_cache_config(self) -> None:
        """Verify configure() accepts CacheConfig."""
        from quadkit.cache.config import CacheConfig

        config = CacheConfig()
        result = CacheModule.configure(config)
        assert isinstance(result, DynamicModule)
        assert result.module is CacheModule

    def test_configure_with_dict(self) -> None:
        """Verify configure() accepts dict configuration."""
        config = {"backend": "memory", "ttl": 300}
        result = CacheModule.configure(config)
        assert isinstance(result, DynamicModule)
        assert result.module is CacheModule

    def test_configure_with_invalid_config(self) -> None:
        """Verify configure() raises TypeError on invalid config."""
        with pytest.raises(TypeError):
            CacheModule.configure("invalid_config")

    def test_configure_exports_cache_backend(self) -> None:
        """Verify configure() exports CacheBackendProtocol."""
        result = CacheModule.configure(None)
        assert CacheBackendProtocol in result.exports
