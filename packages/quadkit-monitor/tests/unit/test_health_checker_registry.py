"""Tests for HealthCheckerRegistry."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from quadkit.monitor.health.checker_registry import HealthCheckerRegistry, get_health_checker
from quadkit.monitor.health.cached import CachedHealthChecker


@pytest.mark.asyncio
async def test_health_checker_registry_lifecycle():
    """Test get_or_create and cleanup."""
    registry = HealthCheckerRegistry()
    
    # 1. Create default
    c1 = registry.get_or_create("default")
    assert isinstance(c1, CachedHealthChecker)
    
    # 2. Get same
    c2 = registry.get_or_create("default")
    assert c1 is c2
    
    # 3. Create another
    c3 = registry.get_or_create("api")
    assert c3 is not c1
    
    # 4. List and Get
    assert registry.get_checker("api") is c3
    assert "default" in registry.list_checkers()
    assert "api" in registry.list_checkers()
    
    # 5. Cleanup
    # Mock stop_background_refresh on checkers
    c1.stop_background_refresh = AsyncMock()
    c3.stop_background_refresh = AsyncMock()
    
    await registry.cleanup()
    c1.stop_background_refresh.assert_called_once()
    c3.stop_background_refresh.assert_called_once()
    assert len(registry.list_checkers()) == 0

@pytest.mark.asyncio
async def test_get_health_checker_utility():
    """Test get_health_checker utility function."""
    mock_registry = MagicMock(spec=HealthCheckerRegistry)
    mock_registry.get_or_create.return_value = MagicMock(spec=CachedHealthChecker)
    
    mock_resolver = MagicMock()
    mock_resolver.resolve = AsyncMock(return_value=mock_registry)
    
    with patch("quadkit.di.resolution.context.get_resolver", return_value=mock_resolver):
        checker = await get_health_checker()
        assert checker is mock_registry.get_or_create.return_value
        mock_resolver.resolve.assert_called_with(HealthCheckerRegistry)

@pytest.mark.asyncio
async def test_get_health_checker_no_resolver():
    """Test get_health_checker error when no resolver is found."""
    with patch("quadkit.di.resolution.context.get_resolver", return_value=None):
        with pytest.raises(ValueError, match="Could not find resolver"):
            await get_health_checker()
