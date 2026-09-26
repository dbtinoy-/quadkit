"""Unit tests for HTTP streaming methods (stream, sse)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.http.client.http_client import HTTPClient
from quadkit.http.config import HTTPClientConfig


class MockAsyncContextManager:
    """Mock async context manager."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class MockStreamContent:
    """Mock aiohttp response content for streaming."""

    def __init__(self, chunks: list[bytes]):
        self.chunks = chunks

    async def iter_chunks(self):
        for chunk in self.chunks:
            if chunk:
                yield (chunk, b"")


class MockStreamResponse:
    """Mock aiohttp response for streaming."""

    def __init__(self, chunks: list[bytes]):
        self.status = 200
        self.chunks = chunks
        self.headers = {"Content-Type": "application/octet-stream"}

    @property
    def url(self):
        return "https://api.example.com/stream"

    @property
    def content(self):
        return MockStreamContent(self.chunks)


@pytest.fixture
def mock_pool():
    """Create mock connection pool."""
    pool = MagicMock()
    pool.session= MagicMock()
    pool.session.request = MagicMock()
    return pool


@pytest.fixture
def http_client(mock_pool):
    """Create HTTPClient with mocked pool."""
    client = HTTPClient(config=HTTPClientConfig(enforce_url_safety=False))
    client._pool = mock_pool
    return client


class TestStreamMethod:
    """Test stream() method for chunked response streaming."""

    @pytest.mark.asyncio
    async def test_stream_chunks_response(self, http_client, mock_pool):
        """Test stream() chunks response body into async iterator."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_response = MockStreamResponse(chunks)
        mock_pool.session.request.return_value = MockAsyncContextManager(mock_response)

        async with http_client.stream("GET", "https://api.example.com/stream") as stream:
            result_chunks = [chunk async for chunk in stream]

        assert len(result_chunks) == 3
        assert result_chunks[0] == b"chunk1"
        assert result_chunks[1] == b"chunk2"
        assert result_chunks[2] == b"chunk3"

    @pytest.mark.asyncio
    async def test_stream_get_method(self, http_client, mock_pool):
        """Test stream() uses GET method by default."""
        mock_response = MockStreamResponse([b"data"])
        mock_pool.session.request.return_value = MockAsyncContextManager(mock_response)

        async with http_client.stream("GET", "https://api.example.com/stream") as stream:
            pass

        mock_pool.session.request.assert_called_once_with(
            "GET", "https://api.example.com/stream"
        )

    @pytest.mark.asyncio
    async def test_stream_post_method(self, http_client, mock_pool):
        """Test stream() supports POST method."""
        mock_response = MockStreamResponse([b"data"])
        mock_pool.session.request.return_value = MockAsyncContextManager(mock_response)

        async with http_client.stream(
            "POST",
            "https://api.example.com/stream",
            json={"query": "test"},
        ) as stream:
            pass

        mock_pool.session.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_raises_when_not_started(self, http_client):
        """Test stream() raises when client not started."""
        http_client._pool.session= None

        from quadkit.http.exceptions import HTTPConnectionError
        with pytest.raises(HTTPConnectionError, match="not started"):
            async with http_client.stream("GET", "https://api.example.com/stream"):
                pass


class TestStreamResponseMethod:
    """Test metadata-preserving raw streaming for protocol gateways."""

    @pytest.mark.asyncio
    async def test_stream_response_exposes_status_headers_and_chunks(self, http_client, mock_pool):
        """A gateway can classify the response without buffering its body."""
        mock_response = MockStreamResponse([b"data: one\\n\\n", b"data: two\\n\\n"])
        mock_response.status = 429
        mock_response.headers = {"Content-Type": "text/event-stream", "Retry-After": "2"}
        mock_pool.session.request.return_value = MockAsyncContextManager(mock_response)

        async with http_client.stream_response(
            "POST",
            "https://api.example.com/stream",
            json={"stream": True},
        ) as response:
            assert response.status == 429
            assert response.headers["Retry-After"] == "2"
            assert [chunk async for chunk in response.aiter_bytes()] == [
                b"data: one\\n\\n",
                b"data: two\\n\\n",
            ]


class TestSSEMethod:
    """Test sse() method for Server-Sent Events."""

    @pytest.mark.asyncio
    async def test_sse_requires_started_session(self, http_client):
        """Test sse() raises when client not started."""
        http_client._pool.session= None

        from quadkit.http.exceptions import HTTPConnectionError
        with pytest.raises(HTTPConnectionError, match="not started"):
            async with http_client.sse("https://api.example.com/events"):
                pass

    @pytest.mark.asyncio
    async def test_sse_sets_event_headers(self, http_client, mock_pool):
        """Test sse() sets appropriate headers."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.content = MagicMock()
        mock_pool.session.request.return_value = MockAsyncContextManager(mock_response)

        async with http_client.sse("https://api.example.com/events") as events:
            pass

        call_kwargs = mock_pool.session.request.call_args
        headers = call_kwargs.kwargs.get("headers", {}) if call_kwargs.kwargs else {}
        assert headers.get("Accept") == "text/event-stream"
        assert headers.get("Cache-Control") == "no-cache"

    @pytest.mark.asyncio
    async def test_sse_uses_get_method(self, http_client, mock_pool):
        """Test sse() always uses GET method."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.content = MagicMock()
        mock_response.url = "https://api.example.com/events"
        mock_pool.session.request.return_value = MockAsyncContextManager(mock_response)

        async with http_client.sse("https://api.example.com/events") as events:
            pass

        call_args = mock_pool.session.request.call_args
        assert call_args.args[0] == "GET"
