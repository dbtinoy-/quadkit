"""Lifecycle tests for quadkit-cache package.

These tests only exercise in-process provider/config construction — they do
**not** require a live Redis or any other external service, so they run in
the default ``-m "not integration"`` suite.
"""

from __future__ import annotations

from quadkit.cache.config import CacheConfig
from quadkit.cache.di.provider import CacheProvider


class TestCacheProviderIntegration:
    """Integration tests for CacheProvider basic functionality."""

    def test_provider_initialization_default(self):
        """Test CacheProvider initialization with default config."""
        provider = CacheProvider()
        assert provider.name == "cache"

    def test_provider_initialization_with_config(self):
        """Test CacheProvider initialization with custom config."""
        config = CacheConfig()
        provider = CacheProvider(config=config)
        assert provider.name == "cache"

    def test_provider_from_config(self):
        """Test CacheProvider from_config factory."""
        config = CacheConfig()
        provider = CacheProvider.from_config(config)
        assert provider.name == "cache"

    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        provider = CacheProvider()
        assert hasattr(provider, "name")
        assert hasattr(provider, "config")

    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        provider = CacheProvider()
        assert provider.priority == ProviderPriority.INFRASTRUCTURE


class TestCacheConfigIntegration:
    """Integration tests for CacheConfig."""

    def test_cache_config_creation(self):
        """Test CacheConfig can be created."""
        config = CacheConfig()
        assert config is not None

    def test_cache_config_model_dump(self):
        """Test CacheConfig model can be serialized."""
        config = CacheConfig()
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)


class TestCacheBackendRegistryIntegration:
    """Integration tests for CacheBackendRegistry."""

    def test_backend_registry_import(self):
        """Test BackendRegistry can be imported."""
        from quadkit.cache.backends.registry import BackendRegistry
        assert BackendRegistry is not None


class TestCacheModuleIntegration:
    """Integration tests for CacheModule."""

    def test_cache_module_import(self):
        """Test CacheModule can be imported."""
        from quadkit.cache.module import CacheModule
        assert CacheModule is not None