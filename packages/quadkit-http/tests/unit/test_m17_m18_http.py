"""Tests for M17 (per-host connection limit) and M18 (ResiliencePipeline hook)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.http.config import ConnectionPoolConfig
from quadkit.http.constants import DEFAULT_MAX_CONNECTIONS_PER_HOST
from quadkit.http.pool.connection_pool import ConnectionPool


class TestM17PerHostConnectionLimit:
    """M17: ConnectionPool respects per-host limit."""

    def test_default_constant_exists(self) -> None:
        """DEFAULT_MAX_CONNECTIONS_PER_HOST is exported from constants."""
        assert DEFAULT_MAX_CONNECTIONS_PER_HOST == 10

    def test_pool_config_default(self) -> None:
        """ConnectionPoolConfig carries max_connections_per_host with default value."""
        config = ConnectionPoolConfig()
        assert config.max_connections_per_host == DEFAULT_MAX_CONNECTIONS_PER_HOST

    def test_pool_config_custom(self) -> None:
        """ConnectionPoolConfig accepts a custom max_connections_per_host."""
        config = ConnectionPoolConfig(max_connections_per_host=25)
        assert config.max_connections_per_host == 25

    def test_connection_pool_stores_per_host_limit(self) -> None:
        """ConnectionPool stores the per-host limit on construction."""
        pool = ConnectionPool(
            max_connections=20,
            max_connections_per_host=5,
        )
        assert pool.max_connections_per_host == 5


class TestM18ResiliencePipelineHook:
    """M18: HTTPClient accepts and uses ResiliencePipelineProtocol."""

    @pytest.mark.asyncio
    async def test_request_routed_through_resilience_pipeline(self) -> None:
        """When resilience is provided, request() delegates to resilience.execute()."""
        from quadkit.contracts.web import HttpResponse
        from quadkit.http.client import HTTPClient
        from quadkit.http.config import HTTPClientConfig

        fake_response = HttpResponse(
            status=200, headers={}, body=b"ok", text="ok",
            json=None, url="http://example.com/test", method="GET",
        )
        resilience = MagicMock()
        resilience.execute = AsyncMock(return_value=fake_response)

        client = HTTPClient(config=HTTPClientConfig(enforce_url_safety=False), resilience=resilience)

        # Patch _to_http_response so we don't need a real aiohttp response
        with patch(
            "quadkit.http.client.http_client._to_http_response",
            new_callable=AsyncMock,
            return_value=fake_response,
        ):
            result = await client.request("GET", "http://example.com/test")

        resilience.execute.assert_awaited_once()
        assert result.status == 200

    @pytest.mark.asyncio
    async def test_no_resilience_uses_retry_policy(self) -> None:
        """Without resilience, request() uses the built-in retry policy."""
        from quadkit.contracts.web import HttpResponse
        from quadkit.http.client import HTTPClient
        from quadkit.http.config import HTTPClientConfig

        fake_response = HttpResponse(
            status=200, headers={}, body=b"", text="",
            json=None, url="http://example.com/test", method="GET",
        )

        client = HTTPClient(config=HTTPClientConfig(enforce_url_safety=False))
        assert client._resilience is None

        with (
            patch.object(
                client._retry_policy, "execute", new_callable=AsyncMock,
                return_value=fake_response,
            ) as mock_retry,
            patch(
                "quadkit.http.client.http_client._to_http_response",
                new_callable=AsyncMock,
                return_value=fake_response,
            ),
        ):
            result = await client.request("GET", "http://example.com/test")

        mock_retry.assert_awaited_once()
        assert result.status == 200

