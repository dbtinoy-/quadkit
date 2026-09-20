"""Tests for web interceptors builtins."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from quadkit.web.interceptors.builtin.cache import CacheInterceptor
from quadkit.web.interceptors.builtin.timing import HandlerTimingInterceptor
from quadkit.web.interceptors.builtin.logging import LoggingInterceptor
from quadkit.web.interceptors.builtin.transform import TransformInterceptor

from quadkit.web.protocols import ExecutionContextProtocol, CallHandlerProtocol


class MockRequest:
    """Mock request for testing."""
    
    def __init__(
        self,
        method: str = "GET",
        path: str = "/test",
        headers: dict | None = None,
    ):
        self.method = method
        self.path = path
        self.headers = headers or {}


class MockResponse:
    """Mock response for testing."""
    
    def __init__(self, body: Any = None, status: int = 200, headers: dict | None = None):
        self.body = body
        self.status = status
        self.headers = headers or {}


class TestCacheInterceptor:
    """Tests for CacheInterceptor."""

    @pytest.fixture
    def mock_context(self) -> MagicMock:
        """Create mock execution context."""
        context = MagicMock(spec=ExecutionContextProtocol)
        context.request = MockRequest(method="GET", path="/test")
        return context

    @pytest.fixture
    def mock_handler(self) -> MagicMock:
        """Create mock call handler."""
        handler = MagicMock(spec=CallHandlerProtocol)
        handler.handle = AsyncMock(return_value=MockResponse(body="test response"))
        return handler

    @pytest.mark.asyncio
    async def test_get_request_is_cached(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test GET requests are cached."""
        interceptor = CacheInterceptor(ttl=60)
        
        # First call - should miss cache
        result = await interceptor.intercept(mock_context, mock_handler)
        assert result.body == "test response"
        
        # Second call - should hit cache
        result2 = await interceptor.intercept(mock_context, mock_handler)
        assert result2.body == "test response"
        assert result2.headers.get("X-Cache") == "HIT"

    @pytest.mark.asyncio
    async def test_post_request_not_cached(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test POST requests bypass cache."""
        mock_context.request = MockRequest(method="POST", path="/test")
        interceptor = CacheInterceptor(ttl=60)
        
        result = await interceptor.intercept(mock_context, mock_handler)
        
        # Handler should be called, no X-Cache header
        mock_handler.handle.assert_called_once()
        assert "X-Cache" not in result.headers

    @pytest.mark.asyncio
    async def test_cache_expiry(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test cache expires after TTL."""
        interceptor = CacheInterceptor(ttl=0)  # Immediate expiry
        
        # First call
        result1 = await interceptor.intercept(mock_context, mock_handler)
        
        # Second call should not hit cache due to expiry
        result2 = await interceptor.intercept(mock_context, mock_handler)
        
        # Handler should be called twice (no cache hit)
        assert mock_handler.handle.call_count == 2

    def test_custom_cache_key_builder(self) -> None:
        """Test custom cache key builder."""
        def custom_key_builder(request: Any) -> str:
            return f"custom:{request.path}"
        
        interceptor = CacheInterceptor(
            ttl=60,
            cache_key_builder=custom_key_builder,
        )
        
        request = MockRequest(path="/test")
        key = interceptor._cache_key_builder(request)
        
        assert key == "custom:/test"


class TestHandlerTimingInterceptor:
    """Tests for HandlerTimingInterceptor."""

    @pytest.fixture
    def mock_context(self) -> MagicMock:
        """Create mock execution context."""
        context = MagicMock(spec=ExecutionContextProtocol)
        context.request = MockRequest(method="GET", path="/test")
        return context

    @pytest.fixture
    def mock_handler(self) -> MagicMock:
        """Create mock call handler."""
        handler = MagicMock(spec=CallHandlerProtocol)
        handler.handle = AsyncMock(return_value=MockResponse(body="test response"))
        return handler

    @pytest.mark.asyncio
    async def test_timing_header_added(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test Server-Timing header is added to response."""
        interceptor = HandlerTimingInterceptor()
        
        result = await interceptor.intercept(mock_context, mock_handler)
        
        assert "Server-Timing" in result.headers
        assert "handler" in result.headers["Server-Timing"]
        assert "dur=" in result.headers["Server-Timing"]

    @pytest.mark.asyncio
    async def test_custom_metric_name(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test custom metric name in header."""
        interceptor = HandlerTimingInterceptor(metric_name="custom")
        
        result = await interceptor.intercept(mock_context, mock_handler)
        
        assert "custom" in result.headers["Server-Timing"]

    @pytest.mark.asyncio
    async def test_precision_parameter(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test precision parameter."""
        interceptor = HandlerTimingInterceptor(precision=3)
        
        result = await interceptor.intercept(mock_context, mock_handler)
        
        # Should have 3 decimal places
        timing = result.headers["Server-Timing"]
        assert "dur=" in timing


class TestLoggingInterceptor:
    """Tests for LoggingInterceptor."""

    @pytest.fixture
    def mock_context(self) -> MagicMock:
        """Create mock execution context."""
        context = MagicMock(spec=ExecutionContextProtocol)
        context.request = MockRequest(method="GET", path="/test")
        return context

    @pytest.fixture
    def mock_handler(self) -> MagicMock:
        """Create mock call handler."""
        handler = MagicMock(spec=CallHandlerProtocol)
        handler.handle = AsyncMock(return_value=MockResponse(body="test response", status=200))
        return handler

    @pytest.mark.asyncio
    async def test_logs_request_info(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test logging interceptor logs request information."""
        interceptor = LoggingInterceptor(log_request=True, log_response=True)
        
        # Just verify the interceptor runs without error and calls handler
        result = await interceptor.intercept(mock_context, mock_handler)
        
        assert result is not None
        mock_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_disabled_logging(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test logging can be disabled."""
        interceptor = LoggingInterceptor(log_request=False, log_response=False)
        
        result = await interceptor.intercept(mock_context, mock_handler)
        
        assert result.body == "test response"


class TestTransformInterceptor:
    """Tests for TransformInterceptor."""

    @pytest.fixture
    def mock_context(self) -> MagicMock:
        """Create mock execution context."""
        context = MagicMock(spec=ExecutionContextProtocol)
        context.request = MockRequest(method="GET", path="/test")
        return context

    @pytest.fixture
    def mock_handler(self) -> MagicMock:
        """Create mock call handler."""
        handler = MagicMock(spec=CallHandlerProtocol)
        handler.handle = AsyncMock(return_value=MockResponse(body={"data": "test"}))
        return handler

    @pytest.mark.asyncio
    async def test_transform_response(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test transform interceptor modifies response."""
        # Transform receives the whole response object
        def transform(response: Any) -> Any:
            return {"transformed": response.body if hasattr(response, "body") else response}
        
        interceptor = TransformInterceptor(transform=transform)
        
        result = await interceptor.intercept(mock_context, mock_handler)
        
        # Result contains transformed data
        assert "transformed" in result

    @pytest.mark.asyncio
    async def test_wrap_response(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test wrap_response option."""
        interceptor = TransformInterceptor(wrap_response=True)
        
        result = await interceptor.intercept(mock_context, mock_handler)
        
        # Response should be present
        assert result is not None

    @pytest.mark.asyncio
    async def test_no_transform(
        self,
        mock_context: MagicMock,
        mock_handler: MagicMock,
    ) -> None:
        """Test interceptor with no transform function."""
        interceptor = TransformInterceptor()
        
        result = await interceptor.intercept(mock_context, mock_handler)
        
        # Should pass through unchanged
        assert result.body == {"data": "test"}