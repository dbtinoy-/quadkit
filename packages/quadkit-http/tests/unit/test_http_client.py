"""Unit tests for HTTP module components."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from quadkit.contracts.infra.resilience.models import RetryConfig
from quadkit.contracts.web import HttpResponse
from quadkit.contracts.web.http_constants import DELETE, GET, POST, PUT
from quadkit.di.module import DynamicModule
from quadkit.http import HTTPModule
from quadkit.http.client.http_client import HTTPClient
from quadkit.http.config import ConnectionPoolConfig, HTTPClientConfig
from quadkit.http.exceptions import HTTPClientError, HTTPTimeoutError
from quadkit.http.pool.connection_pool import ConnectionPool
from quadkit.http.retry.policy import RetryPolicy
from quadkit.http.types import RequestContext, ResponseContext


class TestHTTPModule:
    """Test HTTPModule functionality."""

    def test_module_creation(self):
        """Test module can be created."""
        module = HTTPModule.configure()
        assert module is not None

    def test_module_with_config(self):
        """Test module creation with config."""
        config = HTTPClientConfig()
        module = HTTPModule.configure(config)
        assert module is not None

    def test_module_configure_returns_dynamic_module(self):
        """configure() returns a properly configured DynamicModule."""
        module = HTTPModule.configure()
        assert isinstance(module, DynamicModule)
        assert len(module.providers) > 0

    def test_module_configure_with_config_returns_dynamic_module(self):
        """configure() accepts optional HTTPClientConfig and still returns a DynamicModule."""
        config = HTTPClientConfig()
        module = HTTPModule.configure(config)
        assert isinstance(module, DynamicModule)


class TestHTTPClientConfig:
    """Test HTTP client configuration."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = HTTPClientConfig()
        assert config.proxy is None
        assert config.trust_env is True

    def test_config_with_values(self):
        """Test configuration with custom values."""
        config = HTTPClientConfig(
            proxy="http://proxy.example.com:8080",
            trust_env=False,
            cookie_jar=False,
        )
        assert config.proxy == "http://proxy.example.com:8080"
        assert config.trust_env is False
        assert config.cookie_jar is False


class TestConnectionPoolConfig:
    """Test connection pool configuration."""

    def test_config_defaults(self):
        """Test default pool configuration."""
        config = ConnectionPoolConfig()
        assert config.max_connections == 10
        assert config.max_keepalive_connections == 5

    def test_config_with_values(self):
        """Test pool configuration with custom values."""
        config = ConnectionPoolConfig(
            max_connections=100,
            max_connections_per_host=20,
            timeout=60.0,
        )
        assert config.max_connections == 100
        assert config.max_connections_per_host == 20
        assert config.timeout == 60.0


class TestRetryPolicy:
    """Test retry policy functionality."""

    def test_retry_config_defaults(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0

    def test_retry_config_with_values(self):
        """Test retry configuration with custom values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            backoff_factor=3.0,
        )
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.backoff_factor == 3.0


class TestHTTPClient:
    """Test HTTP client functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock HTTP client."""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_client_creation(self):
        """Test HTTP client can be created."""
        client = HTTPClient()
        assert client is not None

    @pytest.mark.asyncio
    async def test_client_get_request(self, mock_client):
        """Test making GET request."""
        client = HTTPClient()
        client.request = AsyncMock(
            return_value=HttpResponse(status=200, body=b'{"data": "test"}')
        )

        result = await client.get("https://api.example.com/test")
        assert result.is_ok()
        assert result.unwrap().status == 200

    @pytest.mark.asyncio
    async def test_client_post_request(self, mock_client):
        """Test making POST request."""
        client = HTTPClient()
        client.request = AsyncMock(
            return_value=HttpResponse(status=201, body=b'{"created": true}')
        )

        result = await client.post("https://api.example.com/test", json={"data": "test"})
        assert result.is_ok()
        assert result.unwrap().status == 201


class TestConnectionPool:
    """Test connection pool functionality."""

    def test_pool_creation(self):
        """Test connection pool can be created."""
        pool = ConnectionPool(max_connections=10)
        assert pool is not None

    def test_pool_config(self):
        """Test pool has correct configuration."""
        pool = ConnectionPool(max_connections=50, max_keepalive_connections=5)
        assert pool.max_connections == 50
        assert pool.max_keepalive_connections == 5

    @pytest.mark.asyncio
    async def test_pool_is_not_started_before_start(self):
        """Test pool is not started until start() is called."""
        pool = ConnectionPool(max_connections=10)
        assert not pool.is_started()


class TestHTTPMethod:
    """Test HTTP method constants."""

    def test_get_method(self):
        """Test GET constant exists."""
        assert GET is not None
        assert GET == "GET"

    def test_post_method(self):
        """Test POST constant exists."""
        assert POST is not None
        assert POST == "POST"

    def test_put_method(self):
        """Test PUT constant exists."""
        assert PUT is not None
        assert PUT == "PUT"

    def test_delete_method(self):
        """Test DELETE constant exists."""
        assert DELETE is not None
        assert DELETE == "DELETE"


class TestHTTPRequest:
    """Test HTTP request context type."""

    def test_request_creation(self):
        """Test RequestContext can be created."""
        request = RequestContext(
            method="GET",
            url="https://api.example.com/test",
            headers={},
        )
        assert request.method == "GET"
        assert request.url == "https://api.example.com/test"

    def test_request_with_headers(self):
        """Test RequestContext with custom headers."""
        request = RequestContext(
            method="POST",
            url="https://api.example.com/test",
            headers={"Content-Type": "application/json"},
        )
        assert "Content-Type" in request.headers


class TestHTTPResponse:
    """Test HTTP response type."""

    def test_response_creation(self):
        """Test HttpResponse can be created."""
        response = HttpResponse(
            status=200,
            body=b'{"data": "test"}',
        )
        assert response.status == 200
        assert response.body == b'{"data": "test"}'

    def test_response_status_properties(self):
        """Test response Ok property for 2xx."""
        response = HttpResponse(status=200, body=b"")
        assert response.Ok

        error_response = HttpResponse(status=404, body=b"")
        assert not error_response.Ok


class TestHTTPExceptions:
    """Test HTTP exceptions."""

    def test_http_error_creation(self):
        """Test HTTP error can be created."""
        error = HTTPClientError("Request failed")
        assert error.message == "Request failed"

    def test_timeout_error_creation(self):
        """Test timeout error can be created."""
        error = HTTPTimeoutError("Request timed out")
        assert error.message == "Request timed out"
