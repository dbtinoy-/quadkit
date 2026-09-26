"""Tests for cache provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.cache.config import CacheBackendConfig, CacheConfig
from quadkit.cache.di.provider import CacheProvider
from quadkit.testing.clock import FixedClock


class TestCacheProvider:
    """Test suite for CacheProvider."""

    def test_provider_name(self) -> None:
        """Verify provider has correct name."""
        provider = CacheProvider()
        assert provider.name == "cache"

    def test_provider_priority(self) -> None:
        """Verify provider has infrastructure priority."""
        provider = CacheProvider()
        assert provider.priority.value > 0

    def test_provider_config_key(self) -> None:
        """Verify provider has correct config key."""
        provider = CacheProvider()
        assert provider.config_key == "cache"

    def test_provider_config_model(self) -> None:
        """Verify provider has correct config model."""
        provider = CacheProvider()
        assert provider.config_model == CacheConfig

    def test_init_without_config(self) -> None:
        """Verify provider initializes without config."""
        provider = CacheProvider()
        assert provider.config is None
        assert provider._services == {}
        assert provider._backends == {}
        assert provider._serializers == {}

    def test_init_with_config(self) -> None:
        """Verify provider initializes with config."""
        config = CacheConfig()
        provider = CacheProvider(config=config)
        assert provider.config == config

    def test_configure_with_dict(self) -> None:
        """Verify configure accepts dict config."""
        provider = CacheProvider()
        provider.configure({"backends": []})
        assert provider.config is not None

    def test_configure_with_cache_config(self) -> None:
        """Verify configure accepts CacheConfig."""
        provider = CacheProvider()
        config = CacheConfig(
            backends=[CacheBackendConfig(name="test", type="memory", default=True)]
        )
        provider.configure(config)
        assert provider.config == config

    @pytest.mark.asyncio
    async def test_register_binds_backend_registry(self) -> None:
        """Verify register binds backend registry."""
        provider = CacheProvider()
        mock_container = MagicMock()
        mock_container.singleton = MagicMock()
        mock_container.has = MagicMock(return_value=False)
        mock_container.resolve_optional = MagicMock(return_value=None)

        with patch("quadkit.cache.backends.registry.BackendRegistry"):
            await provider.register(mock_container)

        calls = mock_container.singleton.call_args_list
        registered_names = [c[0][0].__name__ for c in calls if hasattr(c[0][0], "__name__")]
        assert "BackendRegistry" in registered_names

    @pytest.mark.asyncio
    async def test_register_binds_cache_provider_protocol(self) -> None:
        """Verify register binds CacheProviderProtocol."""
        provider = CacheProvider()
        mock_container = MagicMock()
        mock_container.singleton = MagicMock()
        mock_container.has = MagicMock(return_value=False)
        mock_container.resolve_optional = MagicMock(return_value=None)

        with patch("quadkit.cache.backends.registry.BackendRegistry"):
            await provider.register(mock_container)

        singleton_calls = mock_container.singleton.call_args_list
        bound_protos = [
            c[0][0].__name__ for c in singleton_calls if hasattr(c[0][0], "__name__")
        ]
        assert "CacheProviderProtocol" in bound_protos or "CacheProvider" in bound_protos

    @pytest.fixture
    def clock(self):
        return FixedClock()

    @pytest.mark.asyncio
    async def test_boot_initializes_backends(self, clock) -> None:
        """Verify boot initializes backends."""
        provider = CacheProvider()
        provider.config = CacheConfig(
            backends=[CacheBackendConfig(name="test", type="memory", default=True)]
        )
        mock_container = MagicMock()
        mock_container.resolve_optional = MagicMock(return_value=None)
        mock_container.resolve = AsyncMock(return_value=clock)

        with patch("quadkit.cache.backends.factory.create_backend", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()
            await provider.boot(mock_container)

    @pytest.mark.asyncio
    async def test_boot_without_config(self, clock) -> None:
        """Verify boot handles missing config."""
        provider = CacheProvider()
        mock_container = MagicMock()
        mock_container.resolve = AsyncMock(return_value=clock)

        await provider.boot(mock_container)
        assert provider._backends == {}

    @pytest.mark.asyncio
    async def test_shutdown_clears_resources(self) -> None:
        """Verify shutdown clears all resources."""
        provider = CacheProvider()
        provider._services = {"test": MagicMock()}
        provider._backends = {"test": MagicMock(close=AsyncMock())}
        provider._serializers = {"test": MagicMock()}

        await provider.shutdown()

        assert provider._services == {}
        assert provider._backends == {}
        assert provider._serializers == {}

    def test_get_default_service_raises_without_config(self) -> None:
        """Verify get_default_service raises without config."""
        provider = CacheProvider()

        with pytest.raises(ValueError, match="not found"):
            provider.get_default_service()

    def test_get_service_unknown_raises(self) -> None:
        """Verify get_service raises for unknown backend."""
        provider = CacheProvider()
        provider.config = CacheConfig()
        provider._services = {}

        with pytest.raises(ValueError, match="not found"):
            provider.get_service("unknown")

    def test_get_backend_unknown_raises(self) -> None:
        """Verify get_backend raises for unknown backend."""
        provider = CacheProvider()
        provider.config = CacheConfig()
        provider._backends = {}

        with pytest.raises(ValueError, match="not found"):
            provider.get_backend("unknown")

    def test_faiss_available_returns_false_when_missing(self) -> None:
        """Verify _faiss_available returns False when faiss missing."""
        provider = CacheProvider()

        with patch("importlib.import_module", side_effect=ImportError):
            result = provider._faiss_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_result(self) -> None:
        """Verify health_check returns HealthCheckResult."""
        provider = CacheProvider()
        result = await provider.health_check()
        assert result is not None
        assert hasattr(result, "status")

    @pytest.mark.asyncio
    async def test_get_metrics_returns_dict(self) -> None:
        """Verify get_metrics returns metrics dict."""
        provider = CacheProvider()
        metrics = await provider.get_metrics()
        assert isinstance(metrics, dict)

    def test_from_config_classmethod(self) -> None:
        """Verify from_config creates configured provider."""
        config = CacheConfig()
        provider = CacheProvider.from_config(config)
        assert provider.config == config

    def test_observe_repository_queues_pair(self) -> None:
        """Verify observe_repository adds observation pair."""
        provider = CacheProvider()
        mock_repo = MagicMock()
        mock_repository = MagicMock()

        provider.observe_repository(mock_repo, mock_repository)
        assert len(provider._observed_pairs) == 1

    def test_cache_property_returns_default_service(self) -> None:
        """Verify cache property returns default service."""
        provider = CacheProvider()
        provider.config = CacheConfig(
            backends=[CacheBackendConfig(name="test", type="memory", default=True)]
        )
        provider._services = {"test": MagicMock()}

        result = provider.cache
        assert result == provider._services["test"]
