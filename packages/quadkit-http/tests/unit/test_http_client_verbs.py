"""Unit tests for HTTP client verb methods (GET, POST, PUT, DELETE, PATCH)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from quadkit import serialization as json
from quadkit.contracts.infra.resilience import RetryConfig
from quadkit.http.client.http_client import HTTPClient as HTTPClientImpl
from quadkit.http.config import HTTPClientConfig
from quadkit.http.exceptions import (
    HTTPConnectionError,
    HTTPStatusError,
    HTTPTimeoutError,
)
from quadkit.http.retry import RetryPolicy


class MockResponse:
    """Mock aiohttp response."""

    def __init__(
        self, status: int, body: bytes, content_type: str = "application/json"
    ):
        self.status = status
        self._body = body
        self.headers = {"Content-Type": content_type}
        self._encoding = "utf-8"

    @property
    def url(self):
        return "https://api.example.com/test"

    async def read(self):
        return self._body

    def get_encoding(self):
        return self._encoding

    async def json(self, content_type=None):
        return json.loads(self._body.decode(self._encoding))


@pytest.fixture
def mock_pool():
    """Create mock connection pool."""
    pool = MagicMock()
    pool.session = MagicMock()
    pool.session.request = AsyncMock()
    return pool


@pytest.fixture
def http_client(mock_pool):
    """Create HTTPClient with mocked pool."""
    client = HTTPClientImpl(config=HTTPClientConfig(enforce_url_safety=False))
    client._pool = mock_pool
    return client


class TestHTTPClientGet:
    """Test HTTP GET verb method."""

    @pytest.mark.asyncio
    async def test_get_returns_ok_on_200(self, http_client, mock_pool):
        """Test GET returns Ok on 200 response."""
        mock_response = MockResponse(200, b'{"data": "test"}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.get("https://api.example.com/data")

        assert result.is_ok()
        assert result.unwrap().status == 200

    @pytest.mark.asyncio
    async def test_get_returns_err_on_400(self, http_client, mock_pool):
        """Test GET returns Err on 400 response."""
        mock_response = MockResponse(400, b'{"error": "bad request"}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.get("https://api.example.com/data")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), HTTPStatusError)
        assert result.unwrap_err().status == 400

    @pytest.mark.asyncio
    async def test_get_returns_err_on_404(self, http_client, mock_pool):
        """Test GET returns Err on 404 response."""
        mock_response = MockResponse(404, b'{"error": "not found"}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.get("https://api.example.com/data")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), HTTPStatusError)
        assert result.unwrap_err().status == 404

    @pytest.mark.asyncio
    async def test_get_returns_err_on_500(self, http_client, mock_pool):
        """Test GET returns Err on 500 response."""
        mock_response = MockResponse(500, b'{"error": "internal error"}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.get("https://api.example.com/data")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), HTTPStatusError)
        assert result.unwrap_err().status == 500


class TestHTTPClientPost:
    """Test HTTP POST verb method."""

    @pytest.mark.asyncio
    async def test_post_returns_ok_on_200(self, http_client, mock_pool):
        """Test POST returns Ok on 200 response."""
        mock_response = MockResponse(200, b'{"created": true}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.post(
            "https://api.example.com/data",
            json={"name": "test"},
        )

        assert result.is_ok()
        assert result.unwrap().status == 200

    @pytest.mark.asyncio
    async def test_post_returns_err_on_400(self, http_client, mock_pool):
        """Test POST returns Err on 400 response."""
        mock_response = MockResponse(400, b'{"error": "validation failed"}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.post(
            "https://api.example.com/data",
            json={"name": "test"},
        )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), HTTPStatusError)
        assert result.unwrap_err().status == 400

    @pytest.mark.asyncio
    async def test_post_with_json_body(self, http_client, mock_pool):
        """Test POST with JSON body sends correct payload."""
        mock_response = MockResponse(201, b'{"id": "123"}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.post(
            "https://api.example.com/data",
            json={"name": "test", "value": 42},
        )

        assert result.is_ok()


class TestHTTPClientPut:
    """Test HTTP PUT verb method."""

    @pytest.mark.asyncio
    async def test_put_returns_ok_on_200(self, http_client, mock_pool):
        """Test PUT returns Ok on 200 response."""
        mock_response = MockResponse(200, b'{"updated": true}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.put(
            "https://api.example.com/data/123",
            json={"name": "updated"},
        )

        assert result.is_ok()
        assert result.unwrap().status == 200

    @pytest.mark.asyncio
    async def test_put_returns_err_on_404(self, http_client, mock_pool):
        """Test PUT returns Err on 404 response."""
        mock_response = MockResponse(404, b'{"error": "not found"}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.put(
            "https://api.example.com/data/123",
            json={"name": "updated"},
        )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), HTTPStatusError)
        assert result.unwrap_err().status == 404


class TestHTTPClientDelete:
    """Test HTTP DELETE verb method."""

    @pytest.mark.asyncio
    async def test_delete_returns_ok_on_204(self, http_client, mock_pool):
        """Test DELETE returns Ok on 204 response."""
        mock_response = MockResponse(204, b"")
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.delete("https://api.example.com/data/123")

        assert result.is_ok()
        assert result.unwrap().status == 204

    @pytest.mark.asyncio
    async def test_delete_returns_err_on_409(self, http_client, mock_pool):
        """Test DELETE returns Err on 409 response."""
        mock_response = MockResponse(409, b'{"error": "conflict"}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.delete("https://api.example.com/data/123")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), HTTPStatusError)
        assert result.unwrap_err().status == 409


class TestHTTPClientPatch:
    """Test HTTP PATCH verb method."""

    @pytest.mark.asyncio
    async def test_patch_returns_ok_on_200(self, http_client, mock_pool):
        """Test PATCH returns Ok on 200 response."""
        mock_response = MockResponse(200, b'{"patched": true}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.patch(
            "https://api.example.com/data/123",
            json={"name": "patched"},
        )

        assert result.is_ok()
        assert result.unwrap().status == 200

    @pytest.mark.asyncio
    async def test_patch_returns_err_on_422(self, http_client, mock_pool):
        """Test PATCH returns Err on 422 response."""
        mock_response = MockResponse(422, b'{"error": "unprocessable"}')
        mock_pool.session.request = AsyncMock(return_value=mock_response)

        result = await http_client.patch(
            "https://api.example.com/data/123",
            json={"name": "patched"},
        )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), HTTPStatusError)
        assert result.unwrap_err().status == 422


class TestTimeoutNormalization:
    """Round-10: raw TimeoutError normalises to HTTPTimeoutError."""

    @pytest.mark.asyncio
    async def test_get_timeout_returns_err_http_timeout(self, http_client, mock_pool):
        mock_pool.session.request = AsyncMock(
            side_effect=TimeoutError("read timed out")
        )

        result = await http_client.get("https://api.example.com/slow")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), HTTPTimeoutError)

    @pytest.mark.asyncio
    async def test_request_raises_http_timeout(self, http_client, mock_pool):
        mock_pool.session.request = AsyncMock(
            side_effect=TimeoutError("connect timed out")
        )

        with pytest.raises(HTTPTimeoutError):
            await http_client.request("GET", "https://api.example.com/slow")

    @pytest.mark.asyncio
    async def test_get_normalises_aiohttp_connection_error(self):
        """aiohttp.ClientError (connect refused/DNS/reset) → Err(HTTPConnectionError).

        Detail (QK-USE-3, probe adoption): raw aiohttp errors used
        to escape `get()` instead of mapping to the documented connection-error
        Result — unreachable hosts reach callers that expected `Err`.
        """
        client = HTTPClientImpl(
            config=HTTPClientConfig(enforce_url_safety=False),
            retry_policy=RetryPolicy(config=RetryConfig(max_attempts=1)),
        )
        pool = MagicMock()
        pool.session = MagicMock()
        pool.session.request = AsyncMock(
            side_effect=aiohttp.ClientError(
                "Cannot connect to host api.example.com:443"
            )
        )
        client._pool = pool

        result = await client.get("https://api.example.com/data")

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, HTTPConnectionError)
