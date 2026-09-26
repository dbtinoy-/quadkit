"""Unit tests for storage driver registry."""

import pytest
from unittest.mock import MagicMock, patch

from quadkit.storage.backends.registry import (
    DriverRegistry,
    DriverFactory,
    _create_memory,
    _create_local,
)
from quadkit.storage import constants as storage_const


class MockDriverConfig:
    def __init__(self, root_dir=None, base_url=None):
        self.root_dir = root_dir
        self.base_url = base_url


class MockConfig:
    def __init__(self, drivers=None):
        self.drivers = drivers or {}
    
    def get(self, key, default=None):
        if isinstance(self.drivers, dict):
            return self.drivers.get(key, default)
        return default


class TestDriverRegistry:
    """Tests for DriverRegistry class."""

    @pytest.fixture
    def registry(self):
        return DriverRegistry()

    def test_initializes_with_default_factories(self, registry):
        """Registry should have all built-in drivers registered."""
        drivers = registry.available_drivers()
        
        assert "memory" in drivers
        assert "local" in drivers

    def test_available_drivers_returns_sorted_list(self, registry):
        """available_drivers should return sorted list."""
        drivers = registry.available_drivers()
        
        assert drivers == sorted(drivers)

    def test_register_custom_driver(self, registry):
        """Can register a custom driver factory."""
        custom_factory = MagicMock()
        
        registry.register("custom", custom_factory)
        
        assert "custom" in registry.available_drivers()

    def test_register_overwrites_existing(self, registry):
        """Register should overwrite existing driver."""
        original_factory = registry.get("memory")
        new_factory = MagicMock()
        
        registry.register("memory", new_factory)
        
        assert registry.get("memory") == new_factory
        assert registry.get("memory") != original_factory

    def test_get_driver_memory(self, registry):
        """get_driver returns memory driver."""
        config = MockConfig()
        
        driver = registry.get_driver("memory", config)
        
        assert driver is not None
        assert type(driver).__name__ == "MemoryDriver"

    def test_get_driver_local(self, registry):
        """get_driver returns local driver."""
        config = MockConfig({
            storage_const.DRIVER_LOCAL: {
                "root_dir": "/tmp/test",
                "base_url": "http://localhost:9000",
            }
        })
        
        driver = registry.get_driver("local", config)
        
        assert driver is not None
        assert type(driver).__name__ == "LocalDriver"

    def test_get_driver_unknown_raises(self, registry):
        """get_driver raises ValueError for unknown driver."""
        config = MockConfig()
        
        with pytest.raises(ValueError) as exc_info:
            registry.get_driver("nonexistent", config)
        
        assert "Unknown storage driver" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_get_driver_includes_available_in_error(self, registry):
        """Error message should list available drivers."""
        config = MockConfig()
        
        with pytest.raises(ValueError) as exc_info:
            registry.get_driver("unknown", config)
        
        available = exc_info.value.args[0]
        assert "memory" in available
        assert "local" in available


class TestCreateMemory:
    """Tests for _create_memory factory."""

    def test_create_memory_returns_driver(self):
        """Factory should return MemoryDriver."""
        config = MockConfig()
        
        driver = _create_memory(config)
        
        assert type(driver).__name__ == "MemoryDriver"


class TestCreateLocal:
    """Tests for _create_local factory."""

    def test_create_local_with_defaults(self):
        """Factory should use defaults when not configured."""
        config = MockConfig()
        
        driver = _create_local(config)
        
        assert type(driver).__name__ == "LocalDriver"

    def test_create_local_with_custom_root_dir(self):
        """Factory should use custom root_dir when provided."""
        from pathlib import Path
        from quadkit.storage import constants as storage_const
        mock_driver_cfg = MagicMock()
        mock_driver_cfg.root_dir = "/custom/path"
        mock_driver_cfg.base_url = "http://localhost:8080"
        
        config = MagicMock()
        config.drivers = {storage_const.DRIVER_LOCAL: mock_driver_cfg}
        
        driver = _create_local(config)
        
        assert str(driver.root_dir) == "/custom/path"

    def test_create_local_with_custom_base_url(self):
        """Factory should use custom base_url when provided."""
        from quadkit.storage import constants as storage_const
        mock_driver_cfg = MagicMock()
        mock_driver_cfg.root_dir = "/tmp/test"
        mock_driver_cfg.base_url = "http://custom:9999/storage"
        
        config = MagicMock()
        config.drivers = {storage_const.DRIVER_LOCAL: mock_driver_cfg}
        
        driver = _create_local(config)
        
        assert driver.base_url == "http://custom:9999/storage"


class TestDriverFactoryType:
    """Tests for DriverFactory type alias."""

    def test_driver_factory_is_callable(self):
        """DriverFactory should be a callable type."""
        assert callable(DriverFactory)


class TestRegistryExtensibility:
    """Tests for registry extensibility."""

    @pytest.fixture
    def registry(self):
        return DriverRegistry()

    def test_can_register_multiple_custom_drivers(self, registry):
        """Can register multiple custom drivers."""
        factory1 = MagicMock()
        factory2 = MagicMock()
        
        registry.register("custom1", factory1)
        registry.register("custom2", factory2)
        
        assert "custom1" in registry.available_drivers()
        assert "custom2" in registry.available_drivers()

    def test_get_returns_registered_factory(self, registry):
        """get returns registered factory."""
        factory = MagicMock()
        
        registry.register("test_driver", factory)
        
        assert registry.get("test_driver") == factory

    def test_get_returns_none_for_unknown(self, registry):
        """get returns None for unknown driver."""
        assert registry.get("unknown_driver") is None
