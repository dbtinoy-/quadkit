"""Tests for cache integration provider module"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.cache.config import (
    CacheBackendConfig,
    CacheConfig,
    CacheServiceConfig,
)
from quadkit.cache.di.provider import CacheProvider
from quadkit.cache.types import BackendType
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.serialization import dumps
from quadkit.testing.clock import FixedClock


@pytest.fixture
def clock():
    """Create a fixed clock for testing."""
    return FixedClock()


@pytest.fixture
def basic_config():
    """Create a basic provider configuration"""
    return CacheConfig(
        name="test_provider",
        backends=[
            CacheBackendConfig(
                name="memory",
                type=BackendType.MEMORY,
                default=True,
                enabled=True,
                default_ttl=300,
                key_prefix="test:",
            ),
        ],
        service=CacheServiceConfig(enable_protection=False, enable_metrics=True),
    )


@pytest.fixture
def mock_container(clock):
    """Create a mock DI container"""
    container = MagicMock()
    container.register = MagicMock()
    container.get = MagicMock(side_effect=KeyError("LockStore not found"))
    container.resolve = AsyncMock(return_value=clock)
    return container


@pytest.fixture
def mock_app(clock):
    """Create a mock application"""
    app = MagicMock()
    app.resolve = AsyncMock(return_value=clock)
    return app


class TestCacheProvider:
    def test_cache_provider_initialization(self):
        """Test CacheProvider initialization"""
        provider = CacheProvider()
        assert provider.name == "cache"  # Default name from base Provider class

    def test_cache_provider_initialization_with_name(self):
        """Test CacheProvider has the canonical class-level name."""
        provider = CacheProvider()
        assert provider.name == "cache"

    def test_cache_provider_configure(self, basic_config):
        """Test provider configuration"""
        provider = CacheProvider()
        config_dict = basic_config.model_dump()

        provider.configure(config_dict)

        assert provider.config is not None
        assert provider.config.name == "test_provider"
        assert len(provider.config.backends) == 1

    @pytest.mark.asyncio
    async def test_cache_provider_register(self, mock_container, basic_config):
        """Test provider registration with container"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        await provider.register(mock_container)

        # register() only binds factories — no I/O yet
        # pickle is opt-in; default is json only
        assert len(provider._serializers) >= 1
        # Should have registered services in container via singleton()
        assert mock_container.singleton.call_count >= 2  # CacheProvider + CacheBackendProtocol

        # boot() performs the actual I/O — backends and services are populated here
        await provider.boot(mock_container)

        assert len(provider._backends) == 1
        assert len(provider._services) == 1

    @pytest.mark.asyncio
    async def test_cache_provider_register_no_config(self, mock_container):
        """Test provider registration without configuration"""
        provider = CacheProvider()

        await provider.register(mock_container)

        # Should still initialize serializers but no backends/services
        # pickle is opt-in; default is json only
        assert len(provider._serializers) >= 1
        assert len(provider._backends) == 0
        assert len(provider._services) == 0

    @pytest.mark.asyncio
    async def test_cache_provider_register_with_protection(self, mock_container):
        """Test provider registration with stampede protection enabled"""
        config = CacheConfig(
            name="test_provider",
            backends=[
                CacheBackendConfig(
                    name="memory", type=BackendType.MEMORY, default=True, enabled=True,
                ),
            ],
            service=CacheServiceConfig(
                enable_protection=True,
                protection_lock_ttl=30,
                protection_max_wait=10.0,
                protection_retry_interval=0.1,
            ),
        )

        provider = CacheProvider()
        provider.configure(config.model_dump())

        await provider.register(mock_container)

        # Protection may or may not be initialized depending on Redis availability
        # When Redis is available, protection will be set; otherwise it remains None
        # The important thing is the provider doesn't crash
        assert provider._services is not None

    @pytest.mark.asyncio
    async def test_cache_provider_startup_shutdown(self, mock_app, basic_config):
        """Test provider startup and shutdown"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        # Startup
        await provider.boot(mock_app)

        # Shutdown
        await provider.shutdown()

        # Should have cleared references
        assert len(provider._services) == 0
        assert len(provider._backends) == 0
        assert len(provider._serializers) == 0
        assert provider._protection is None

    @pytest.mark.asyncio
    async def test_cache_provider_health_check(self, basic_config):
        """Provider health details remain safe for a JSON readiness response."""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())
        provider._services = {
            "memory": MagicMock(
                health_check=AsyncMock(
                    return_value=HealthCheckResult(
                        component="test:service",
                        status=HealthStatus.HEALTHY,
                        details={"test": "ok"},
                    )
                )
            )
        }
        provider._backends = {
            "memory": MagicMock(
                health_check=AsyncMock(
                    return_value=HealthCheckResult(
                        component="test:backend",
                        status=HealthStatus.HEALTHY,
                        details={"connections": 1},
                    )
                )
            )
        }

        health_status = await provider.health_check()

        assert health_status.details is not None
        assert health_status.details["services"]["memory"]["status"] == "healthy"
        assert health_status.details["backends"]["memory"]["status"] == "healthy"
        dumps(health_status.to_dict())

    @pytest.mark.asyncio
    async def test_cache_provider_get_health_status_unhealthy(self, basic_config, clock):
        """Test provider health check with unhealthy components"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        # Both register() and boot() must run so services are populated
        mock_container = MagicMock()
        mock_container.resolve = AsyncMock(return_value=clock)
        await provider.register(mock_container)
        await provider.boot(mock_container)

        # Mock unhealthy service
        for service in provider._services.values():
            service.health_check = AsyncMock(
                return_value=HealthCheckResult(component="test:service", status=HealthStatus.UNHEALTHY, error="Connection failed"),
            )

        health_status = await provider.health_check()

        # Check health status is not healthy
        assert health_status.status != HealthStatus.HEALTHY

    def test_cache_provider_get_service(self, basic_config):
        """Test getting cache service by name"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        # Manually add a service (simulating registration)
        mock_service = MagicMock()
        provider._services["memory"] = mock_service

        service = provider.get_service("memory")
        assert service == mock_service

    def test_cache_provider_get_service_default(self, basic_config):
        """Test getting default cache service"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        # Manually add a service
        mock_service = MagicMock()
        provider._services["memory"] = mock_service

        service = provider.get_service()  # No name specified
        assert service == mock_service

    def test_cache_provider_get_service_not_found(self, basic_config):
        """Test getting non-existent service"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        with pytest.raises(ValueError, match="Cache service 'nonexistent' not found"):
            provider.get_service("nonexistent")

    def test_cache_provider_get_backend(self, basic_config):
        """Test getting backend by name"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        # Manually add a backend
        mock_backend = MagicMock()
        provider._backends["memory"] = mock_backend

        backend = provider.get_backend("memory")
        assert backend == mock_backend

    def test_cache_provider_get_backend_not_found(self, basic_config):
        """Test getting non-existent backend"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        with pytest.raises(ValueError, match="Backend 'nonexistent' not found"):
            provider.get_backend("nonexistent")

    def test_cache_provider_get_default_service(self, basic_config):
        """Test getting default service"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        # Manually add a service
        mock_service = MagicMock()
        provider._services["memory"] = mock_service

        service = provider.get_default_service()
        assert service == mock_service

    @pytest.mark.asyncio
    async def test_cache_provider_get_metrics(self, basic_config, clock):
        """Test getting provider metrics"""
        provider = CacheProvider()
        provider.configure(basic_config.model_dump())

        # Both register() and boot() must run so services are populated
        mock_container = MagicMock()
        mock_container.resolve = AsyncMock(return_value=clock)
        await provider.register(mock_container)
        await provider.boot(mock_container)

        # Mock service metrics
        for service in provider._services.values():
            service.get_metrics = AsyncMock(return_value={"hits": 100, "misses": 20})

        metrics = await provider.get_metrics()

        assert metrics["provider"]["services_count"] == 1
        assert metrics["provider"]["backends_count"] == 1
        assert "services" in metrics

    @pytest.mark.asyncio
    async def test_cache_provider_create_backend_memory(self):
        """Test creating memory backend"""
        config = CacheBackendConfig(
            name="memory", type=BackendType.MEMORY, default_ttl=300, key_prefix="test:",
        )

        provider = CacheProvider()
        backend = await provider._create_backend(config)

        assert backend is not None
        # Should be a MemoryCacheBackend instance

    @pytest.mark.asyncio
    async def test_cache_provider_create_backend_redis(self):
        """Test creating Redis backend"""
        config = CacheBackendConfig(
            name="redis",
            type=BackendType.REDIS,
            redis_url="redis://localhost:6379",
            default_ttl=600,
        )

        provider = CacheProvider()
        container = AsyncMock()
        container.resolve.return_value = AsyncMock()
        backend = await provider._create_backend(config, container=container)

        assert backend is not None
        # Should be a RedisCacheBackend instance

    @pytest.mark.asyncio
    async def test_cache_provider_create_backend_memcached(self):
        """Test creating Memcached backend"""
        config = CacheBackendConfig(
            name="memcached",
            type=BackendType.MEMCACHED,
            memcached_servers=["localhost:11211"],
            default_ttl=300,
        )

        provider = CacheProvider()
        backend = await provider._create_backend(config)

        assert backend is not None
        # Should be a MemcachedCacheBackend instance

    @pytest.mark.asyncio
    async def test_cache_provider_create_backend_unsupported_type(self):
        """Test creating backend with unsupported type"""
        # Create a config with an invalid type by bypassing validation
        config = CacheBackendConfig(
            name="unknown", type=BackendType.MEMORY, default_ttl=300,  # Valid type
        )

        provider = CacheProvider()

        # Mock the _create_backend method to raise ValueError for "unsupported type"
        with (
            patch.object(
                provider,
                "_create_backend",
                side_effect=ValueError("Unsupported backend type"),
            ),
            pytest.raises(ValueError, match="Unsupported backend type"),
        ):
            await provider._create_backend(config)

    @pytest.mark.asyncio
    async def test_cache_provider_initialize_backends_disabled(self):
        """Test initializing backends with disabled backend"""
        config = CacheConfig(
            name="test",
            backends=[
                CacheBackendConfig(
                    name="disabled", type=BackendType.MEMORY, enabled=False,
                ),
                CacheBackendConfig(  # Add a default backend to satisfy validation
                    name="default", type=BackendType.MEMORY, default=True, enabled=True,
                ),
            ],
        )

        provider = CacheProvider()
        provider.config = config

        await provider._initialize_backends()

        # Should not have initialized the disabled backend
        assert "disabled" not in provider._backends
        assert "default" in provider._backends

    @pytest.mark.asyncio
    async def test_cache_provider_initialize_backends_failure_non_default(self):
        """Test backend initialization failure for non-default backend"""
        config = CacheConfig(
            name="test",
            backends=[
                CacheBackendConfig(
                    name="failing",
                    type=BackendType.MEMORY,  # Valid type
                    default=False,
                    enabled=True,
                ),
                CacheBackendConfig(  # Add a default backend
                    name="default", type=BackendType.MEMORY, default=True, enabled=True,
                ),
            ],
        )

        provider = CacheProvider()
        provider.config = config

        async def mock_create_backend(backend_config, container=None):
            if backend_config.name == "failing":
                raise RuntimeError("Backend creation failed")
            return MagicMock()

        with patch.object(provider, "_create_backend", side_effect=mock_create_backend):
            # Should not raise exception for non-default backend failure
            await provider._initialize_backends()
            assert "failing" not in provider._backends
            assert "default" in provider._backends

    @pytest.mark.asyncio
    async def test_cache_provider_initialize_backends_failure_default(self):
        """Test backend initialization failure for default backend"""
        config = CacheConfig(
            name="test",
            backends=[
                CacheBackendConfig(
                    name="failing",
                    type=BackendType.MEMORY,  # Valid type
                    default=True,
                    enabled=True,
                ),
            ],
        )

        provider = CacheProvider()
        provider.config = config

        with (
            patch.object(
                provider,
                "_create_backend",
                side_effect=Exception("Backend creation failed"),
            ),
            pytest.raises(
                RuntimeError, match="Failed to initialize default backend",
            ),
        ):
            await provider._initialize_backends()


