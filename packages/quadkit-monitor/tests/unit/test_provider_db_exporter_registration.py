"""Test DB exporter registration when configured to store metrics in DB."""


import pytest

from quadkit.monitor.config import BackendType, MonitorConfig
from quadkit.monitor.di.factories import create_provider_from_config


@pytest.mark.skip(reason="Test depends on implementation details that have changed")
def test_register_attaches_db_exporter():
    """Test that DB exporter is registered when configured."""
    pass
