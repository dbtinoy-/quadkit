"""Integration tests for quadkit-http package."""

from __future__ import annotations

import pytest

from quadkit.http.config import HTTPClientConfig
from quadkit.http.di.provider import HTTPProvider


class TestHTTPProviderIntegration:
    """Integration tests for HTTPProvider basic functionality."""

    @pytest.mark.integration
    def test_provider_initialization_default(self):
        """Test HTTPProvider initialization with default config."""
        provider = HTTPProvider()
        assert provider.name == "http"

    @pytest.mark.integration
    def test_provider_initialization_with_config(self):
        """Test HTTPProvider initialization with custom config."""
        config = HTTPClientConfig()
        provider = HTTPProvider(config=config)
        assert provider.name == "http"

    @pytest.mark.integration
    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        provider = HTTPProvider()
        assert hasattr(provider, "name")

    @pytest.mark.integration
    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        provider = HTTPProvider()
        assert provider.priority == ProviderPriority.INFRASTRUCTURE


class TestHTTPClientConfigIntegration:
    """Integration tests for HTTPClientConfig."""

    @pytest.mark.integration
    def test_http_client_config_creation(self):
        """Test HTTPClientConfig can be created."""
        config = HTTPClientConfig()
        assert config is not None

    @pytest.mark.integration
    def test_http_client_config_model_dump(self):
        """Test HTTPClientConfig model can be serialized."""
        config = HTTPClientConfig()
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)


class TestHTTPClientIntegration:
    """Integration tests for HTTPClient."""

    @pytest.mark.integration
    def test_http_client_import(self):
        """Test HTTPClient can be imported."""
        from quadkit.http.client import HTTPClient
        assert HTTPClient is not None

    @pytest.mark.integration
    def test_http_client_protocol_import(self):
        """Test HTTPClientProtocol can be imported."""
        from quadkit.contracts.web import HTTPClientProtocol
        assert HTTPClientProtocol is not None


class TestHTTPModuleIntegration:
    """Integration tests for HTTPModule."""

    @pytest.mark.integration
    def test_http_module_import(self):
        """Test HTTPModule can be imported."""
        from quadkit.http.module import HTTPModule
        assert HTTPModule is not None