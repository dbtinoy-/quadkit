"""Tests for MonitorBackendRegistryManager."""

import pytest

pytest.importorskip("opentelemetry", reason="Requires opentelemetry")
from unittest.mock import MagicMock
from quadkit.monitor.backends.registry import (
    MonitorBackendRegistryManager,
    PrometheusBackendRegistry,
    OpenTelemetryBackendRegistry,
    MemoryBackendRegistry,
)
from quadkit.monitor.config import MonitorConfig, BackendType


def test_monitor_backend_registry_manager_defaults():
    """Test with_defaults."""
    manager = MonitorBackendRegistryManager.with_defaults()
    assert manager.get(str(BackendType.PROMETHEUS)) is not None
    assert manager.get(str(BackendType.OPENTELEMETRY)) is not None
    assert manager.get(str(BackendType.MEMORY)) is not None

def test_prometheus_backend_registry():
    """Test Prometheus backend creation via registry."""
    pytest.importorskip("prometheus_client", reason="Prometheus backend requires prometheus_client")
    registry = PrometheusBackendRegistry()
    assert registry.can_create(BackendType.PROMETHEUS)
    assert not registry.can_create(BackendType.OPENTELEMETRY)
    
    config = MagicMock(spec=MonitorConfig)
    config.prometheus = MagicMock()
    config.prometheus.port = 9090
    
    backend = registry.create_backend(config)
    assert backend.port == 9090

def test_otel_backend_registry():
    """Test OTel backend creation via registry."""
    registry = OpenTelemetryBackendRegistry()
    assert registry.can_create(BackendType.OPENTELEMETRY)
    
    config = MagicMock(spec=MonitorConfig)
    config.opentelemetry = {"service_name": "test", "endpoint": "localhost"}
    
    backend = registry.create_backend(config)
    assert backend.service_name == "test"
    assert backend.endpoint == "localhost"

def test_monitor_backend_registry_manager_register():
    """Test register methods."""
    manager = MonitorBackendRegistryManager()
    
    # 1. Register with key/value
    custom_registry = MagicMock()
    manager.register(key="custom", value=custom_registry)
    assert manager.get("custom") is custom_registry
    
    # 2. Register with auto-detect (legacy)
    prom_reg = PrometheusBackendRegistry()
    manager.register(prom_reg)
    assert manager.get(str(BackendType.PROMETHEUS)) is prom_reg
    
    # 3. Register error
    uncooperative_factory = MagicMock()
    uncooperative_factory.can_create.return_value = False
    with pytest.raises(ValueError, match="Cannot infer"):
        manager.register(uncooperative_factory)
    
    with pytest.raises(ValueError, match="requires either"):
        manager.register()

def test_monitor_backend_registry_manager_create_backend():
    """Test create_backend through manager."""
    pytest.importorskip("prometheus_client", reason="Prometheus backend requires prometheus_client")
    manager = MonitorBackendRegistryManager.with_defaults()
    config = MagicMock(spec=MonitorConfig)
    config.prometheus = {"port": 8000}
    
    backend = manager.create_backend(BackendType.PROMETHEUS, config)
    assert backend.port == 8000
    
    with pytest.raises(ValueError, match="Unknown monitoring backend"):
        manager.create_backend("unknown", config)
