"""Tests for MonitorProvider creation from config"""

import pytest

from quadkit.monitor.config import BackendType, MonitorConfig
from quadkit.monitor.di.factories import create_provider_from_config


def test_create_prometheus_provider_from_config(monkeypatch):
    pytest.importorskip("prometheus_client", reason="Prometheus backend requires prometheus_client")
    cfg = MonitorConfig(backend_type=BackendType.PROMETHEUS)
    provider = create_provider_from_config(cfg)
    assert provider is not None
    # If prometheus-client installed, exporter should be attached
    try:
        from quadkit.monitor.backends.exporters import (
            HAS_PROMETHEUS,
        )

        if HAS_PROMETHEUS:
            assert getattr(provider, "metrics_exporter", None) is not None

            # Also assert that registering provider with a container exposes MetricsExporter
            class DummyCont:
                def __init__(self):
                    self.mapping = {}

                def singleton(self, key, factory):
                    value = factory() if callable(factory) else factory
                    self.mapping[key] = value

            dummy = DummyCont()
            import asyncio
            asyncio.get_event_loop().run_until_complete(provider.register(dummy))  # register should not fail
            # If exporter present, it should have attempted to register MetricsExporter in container
            assert any(
                "MetricsExporter" in str(k) or k.__name__ == "MetricsExporter"
                for k in dummy.mapping.keys()
            )
    except (ImportError, RuntimeError):
        pass
