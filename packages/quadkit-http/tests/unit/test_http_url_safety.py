"""Tests for the HTTP client SSRF safety gate."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.http.client.base_url_client import BaseURLHTTPClient
from quadkit.http.client.http_client import HTTPClient
from quadkit.http.config import HTTPClientConfig
from quadkit.http.exceptions import HTTPUnsafeURLError


class TestEnforceUrlSafetyConfig:
    """HTTPClientConfig.enforce_url_safety defaults and opt-out."""

    def test_config_default_true(self) -> None:
        """The safety gate is on by default."""
        assert HTTPClientConfig().enforce_url_safety is True

    def test_config_opt_out(self) -> None:
        """The gate can be explicitly disabled for trusted targets."""
        assert HTTPClientConfig(enforce_url_safety=False).enforce_url_safety is False


class _MockPool:
    """Pool whose session request is recorded and never really invoked."""

    def __init__(self) -> None:
        self.session= MagicMock()
        self.session.request = AsyncMock()


def _client(enforce: bool = True) -> HTTPClient:
    client = HTTPClient(config=HTTPClientConfig(enforce_url_safety=enforce))
    client._pool = _MockPool()
    return client


class TestRequestGate:
    """request() rejects unsafe URLs before any connection is attempted."""

    @pytest.mark.asyncio
    async def test_private_ip_literal_rejected(self) -> None:
        client = _client()
        with pytest.raises(HTTPUnsafeURLError):
            await client.request("GET", "http://127.0.0.1/admin")
        client._pool.session.request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_metadata_ip_literal_rejected(self) -> None:
        client = _client()
        with pytest.raises(HTTPUnsafeURLError):
            await client.request("GET", "http://169.254.169.254/latest/meta-data/")
        client._pool.session.request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_public_ip_literal_proceeds(self) -> None:
        client = _client()
        response = MagicMock()
        response.status = 200
        response.read = AsyncMock(return_value=b"{}")
        response.get_encoding = MagicMock(return_value="utf-8")
        response.headers = {"Content-Type": "application/json"}
        response.url = "http://93.184.216.34/"
        response.json = AsyncMock(return_value={})
        client._pool.session.request = AsyncMock(return_value=response)

        result = await client.request("GET", "http://93.184.216.34/")
        assert result.status == 200
        client._pool.session.request.assert_awaited()

    @pytest.mark.asyncio
    async def test_opt_out_bypasses_gate(self) -> None:
        client = _client(enforce=False)
        response = MagicMock()
        response.status = 200
        response.read = AsyncMock(return_value=b"{}")
        response.get_encoding = MagicMock(return_value="utf-8")
        response.headers = {"Content-Type": "application/json"}
        response.url = "http://127.0.0.1/admin"
        response.json = AsyncMock(return_value={})
        client._pool.session.request = AsyncMock(return_value=response)

        result = await client.request("GET", "http://127.0.0.1/admin")
        assert result.status == 200
        client._pool.session.request.assert_awaited()


class TestStreamingGate:
    """stream() and sse() reject unsafe URLs (bypass closure)."""

    @pytest.mark.asyncio
    async def test_stream_rejects_private_literal(self) -> None:
        client = _client()
        with pytest.raises(HTTPUnsafeURLError):
            async with client.stream("GET", "http://127.0.0.1/stream"):
                pass  # pragma: no cover
        client._pool.session.request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sse_rejects_private_literal(self) -> None:
        client = _client()
        with pytest.raises(HTTPUnsafeURLError):
            async with client.sse("http://127.0.0.1/events"):
                pass  # pragma: no cover
        client._pool.session.request.assert_not_awaited()


class TestBaseUrlClientGate:
    """BaseURLHTTPClient.stream() rejects unsafe URLs (bypass closure)."""

    @pytest.mark.asyncio
    async def test_stream_rejects_private_literal(self) -> None:
        buc = BaseURLHTTPClient(base_url="http://127.0.0.1")
        client = _client()
        buc._client = client
        with pytest.raises(HTTPUnsafeURLError):
            async with buc.stream("POST", "/completions"):
                pass  # pragma: no cover
        client._pool.session.request.assert_not_awaited()
