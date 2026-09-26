"""Tests for monitor module."""

import pytest
from quadkit.monitor import MonitorModule
from quadkit.di.module import DynamicModule


class TestMonitorModule:
    def test_monitor_module_exists(self) -> None:
        assert MonitorModule is not None

    def test_configure_defaults_to_noop_backend(self) -> None:
        """configure() with no backend defaults to NoOpMetricsBackend."""
        from quadkit.observability.core import NoOpMetricsBackend

        result = MonitorModule.configure(None)
        assert isinstance(result, DynamicModule)
        provider = result.providers[0]
        assert isinstance(provider.backend, NoOpMetricsBackend)
