"""
Unit tests for cache service layer.
"""

from unittest.mock import AsyncMock, Mock

import pytest

# Import types needed for specs
from quadkit.cache.di import CacheProvider
from quadkit.cache.service.core import CacheService
from quadkit.contracts.core import HealthCheckResult, HealthStatus


class TestCacheServiceBasic:
    """Basic tests for CacheService functionality using mocks."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock cache provider."""
        provider = Mock()
        mock_backend = AsyncMock()
        provider.get_backend.return_value = mock_backend
        provider.health_check = AsyncMock(
            return_value={
                "status": "healthy",
                "backends": {"memory": {"status": "healthy"}},
                "default_backend": "memory",
            },
        )
        return provider

    @pytest.fixture
    def cache_service(self, mock_provider):
        """Create a cache service instance with mocked dependencies."""
        # Import here to avoid module-level imports
        from quadkit.cache.service.core import CacheService

        return CacheService(mock_provider)

    @pytest.mark.asyncio
    async def test_get_success(self, cache_service, mock_provider):
        """Test successful get operation."""
        mock_backend = mock_provider.get_backend.return_value
        mock_backend.get.return_value = "test_value"

        result = await cache_service.get("test_key")

        assert result == "test_value"
        mock_backend.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_with_default(self, cache_service, mock_provider):
        """Test get operation with default value."""
        mock_backend = mock_provider.get_backend.return_value
        mock_backend.get.return_value = None

        result = await cache_service.get("test_key", default="default_value")

        assert result == "default_value"
        mock_backend.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_set_success(self, cache_service, mock_provider):
        """Test successful set operation."""
        mock_backend = mock_provider.get_backend.return_value
        mock_backend.set.return_value = True

        result = await cache_service.set("test_key", "test_value")

        assert result is True
        mock_backend.set.assert_called_once_with("test_key", "test_value", None)


class TestCacheService:
    """Test CacheService functionality."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock cache provider."""
        provider = Mock(spec=CacheProvider)
        mock_backend = AsyncMock()
        provider.get_backend.return_value = mock_backend
        provider.health_check = AsyncMock(
            return_value={
                "status": "healthy",
                "backends": {"memory": {"status": "healthy"}},
                "default_backend": "memory",
            },
        )
        return provider

    @pytest.fixture
    def cache_service(self, mock_provider):
        """Create a cache service instance with mocked dispatcher."""
        return CacheService(mock_provider)

    @pytest.mark.asyncio
    async def test_get_success(self, cache_service, mock_provider):
        """Test successful get operation."""
        mock_backend = mock_provider.get_backend.return_value
        mock_backend.get.return_value = "test_value"

        result = await cache_service.get("test_key")

        assert result == "test_value"
        mock_backend.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_with_default(self, cache_service, mock_provider):
        """Test get operation with default value."""
        mock_backend = mock_provider.get_backend.return_value
        mock_backend.get.return_value = None

        result = await cache_service.get("test_key", default="default_value")

        assert result == "default_value"
        mock_backend.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_set_success(self, cache_service, mock_provider):
        """Test successful set operation."""
        mock_backend = mock_provider.get_backend.return_value
        mock_backend.set.return_value = True

        result = await cache_service.set("test_key", "test_value")

        assert result is True
        mock_backend.set.assert_called_once_with("test_key", "test_value", None)

    @pytest.mark.asyncio
    async def test_set_with_ttl_jitter(self, cache_service, mock_provider):
        """Test that TTL jitter is applied to prevent cache stampede."""
        mock_backend = mock_provider.get_backend.return_value
        mock_backend.set.return_value = True

        # Test with a fixed TTL
        result = await cache_service.set("test_key", "test_value", ttl=300)

        assert result is True
        # Verify that set was called with a TTL (jittered from 300)
        call_args = mock_backend.set.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == "test_value"
        actual_ttl = call_args[0][2]
        # TTL should be between 270 and 330 (300 ± 10%)
        assert 270 <= actual_ttl <= 330

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache_service, mock_provider):
        """Test get_or_set when value is cached."""
        mock_backend = mock_provider.get_backend.return_value
        mock_backend.get.return_value = "cached_value"

        result = await cache_service.get_or_set("test_key", lambda: "computed_value")

        assert result == "cached_value"
        mock_backend.get.assert_called_once_with("test_key")
        mock_backend.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache_service, mock_provider):
        """Test get_or_set when value needs to be computed."""
        mock_backend = mock_provider.get_backend.return_value
        mock_backend.get.return_value = None
        mock_backend.set.return_value = True

        result = await cache_service.get_or_set("test_key", lambda: "computed_value")

        assert result == "computed_value"
        mock_backend.get.assert_called_once_with("test_key")
        mock_backend.set.assert_called_once_with("test_key", "computed_value", None)

    @pytest.mark.asyncio
    async def test_health_check_probes_backend_without_reentering_provider(
        self, cache_service, mock_provider
    ):
        """A provider aggregate must not recurse through its services."""
        backend = mock_provider.get_backend.return_value
        backend.health_check = AsyncMock(
            return_value=HealthCheckResult(
                component="cache:memory", status=HealthStatus.HEALTHY
            )
        )
        mock_provider.health_check.side_effect = AssertionError(
            "CacheService must not call provider.health_check()"
        )

        result = await cache_service.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.details is not None
        assert result.details["backends"]["default"]["status"] == "healthy"
        assert "service" in result.details
        assert "operations" in result.details["service"]
        assert "hits" in result.details["service"]
        assert "misses" in result.details["service"]
        assert "errors" in result.details["service"]
        backend.health_check.assert_awaited_once_with(5.0)
        mock_provider.health_check.assert_not_called()

    def test_metrics_tracking(self, cache_service, mock_provider):
        """Test that metrics are tracked correctly."""
        metrics = cache_service.get_metrics()

        assert "operations" in metrics
        assert "hits" in metrics
        assert "misses" in metrics
        assert "errors" in metrics
        assert metrics["operations"] == 0
        assert metrics["hits"] == 0
        assert metrics["misses"] == 0
        assert metrics["errors"] == 0

    def test_reset_metrics(self, cache_service):
        """Test metrics reset functionality."""
        cache_service._metrics["operations"] = 10
        cache_service.reset_metrics()

        metrics = cache_service.get_metrics()
        assert metrics["operations"] == 0
