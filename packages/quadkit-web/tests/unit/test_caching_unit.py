"""Unit tests for quadkit.web.caching module."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock
from starlette.requests import Request
from starlette.responses import Response

from quadkit.web.routing.caching import cache_control, etag, _etag_matches


class TestCacheControl:
    """Tests for the @cache_control decorator."""

    @pytest.mark.asyncio
    async def test_cache_control_sets_header_on_response(self) -> None:
        """Verify Cache-Control header is set on Response objects."""

        @cache_control(max_age=3600, public=True)
        async def handler() -> Response:
            return Response(content=b"test", status_code=200)

        result = await handler()
        assert result.headers["Cache-Control"] == "public, max-age=3600"

    @pytest.mark.asyncio
    async def test_cache_control_private_option(self) -> None:
        """Verify private option is correctly applied."""

        @cache_control(private=True)
        async def handler() -> Response:
            return Response(content=b"test", status_code=200)

        result = await handler()
        assert "private" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_cache_control_no_store(self) -> None:
        """Verify no-store disables caching."""

        @cache_control(no_store=True)
        async def handler() -> Response:
            return Response(content=b"test", status_code=200)

        result = await handler()
        assert "no-store" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_cache_control_no_cache(self) -> None:
        """Verify no-cache forces revalidation."""

        @cache_control(no_cache=True)
        async def handler() -> Response:
            return Response(content=b"test", status_code=200)

        result = await handler()
        assert "no-cache" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_cache_control_must_revalidate(self) -> None:
        """Verify must-revalidate is applied."""

        @cache_control(must_revalidate=True)
        async def handler() -> Response:
            return Response(content=b"test", status_code=200)

        result = await handler()
        assert "must-revalidate" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_cache_control_immutable(self) -> None:
        """Verify immutable hint is applied."""

        @cache_control(immutable=True)
        async def handler() -> Response:
            return Response(content=b"test", status_code=200)

        result = await handler()
        assert "immutable" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_cache_control_s_maxage(self) -> None:
        """Verify s-maxage for shared caches."""

        @cache_control(s_maxage=7200, public=True)
        async def handler() -> Response:
            return Response(content=b"test", status_code=200)

        result = await handler()
        assert "s-maxage=7200" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_cache_control_stale_while_revalidate(self) -> None:
        """Verify stale-while-revalidate directive."""

        @cache_control(stale_while_revalidate=60, public=True)
        async def handler() -> Response:
            return Response(content=b"test", status_code=200)

        result = await handler()
        assert "stale-while-revalidate=60" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_cache_control_no_arguments_defaults_to_no_cache(self) -> None:
        """Verify default behavior when no arguments provided."""

        @cache_control()
        async def handler() -> Response:
            return Response(content=b"test", status_code=200)

        result = await handler()
        assert result.headers["Cache-Control"] == "no-cache"

    @pytest.mark.asyncio
    async def test_cache_control_skips_non_response(self) -> None:
        """Verify decorator works with non-Response return values."""

        @cache_control(max_age=60)
        async def handler() -> dict[str, str]:
            return {"data": "test"}

        result = await handler()
        assert isinstance(result, dict)


class TestETag:
    """Tests for the @etag decorator."""

    @pytest.mark.asyncio
    async def test_etag_sets_header_on_response(self) -> None:
        """Verify ETag header is generated and set on Response."""

        @etag
        async def handler() -> Response:
            return Response(content=b"test content", status_code=200)

        result = await handler()
        assert "ETag" in result.headers
        assert result.headers["ETag"].startswith('W/"')

    @pytest.mark.asyncio
    async def test_etag_304_not_modified_when_match(self) -> None:
        """Verify 304 returned when If-None-Match matches."""

        @etag
        async def handler(request: Request) -> Response:
            return Response(content=b"test content", status_code=200)

        # Create mock request with matching ETag (MD5 of "test content" = 9473fdd0d880a43c21b7778d34872157)
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"If-None-Match": 'W/"9473fdd0d880a43c21b7778d34872157"'}

        result = await handler(mock_request)
        assert result.status_code == 304

    @pytest.mark.asyncio
    async def test_etag_returns_full_response_when_no_match(self) -> None:
        """Verify full response when If-None-Match doesn't match."""

        @etag
        async def handler(request: Request) -> Response:
            return Response(content=b"test content", status_code=200)

        # Create mock request with non-matching ETag
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"If-None-Match": "different-etag"}

        result = await handler(mock_request)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_etag_handles_star_wildcard(self) -> None:
        """Verify * wildcard matches any ETag."""

        @etag
        async def handler(request: Request) -> Response:
            return Response(content=b"test content", status_code=200)

        # Create mock request with * wildcard
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"If-None-Match": "*"}

        result = await handler(mock_request)
        assert result.status_code == 304

    @pytest.mark.asyncio
    async def test_etag_empty_if_none_match(self) -> None:
        """Verify full response when no If-None-Match header."""

        @etag
        async def handler(request: Request) -> Response:
            return Response(content=b"test content", status_code=200)

        # Create mock request without If-None-Match
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}

        result = await handler(mock_request)
        assert result.status_code == 200
        assert "ETag" in result.headers

    @pytest.mark.asyncio
    async def test_etag_skips_non_response(self) -> None:
        """Verify decorator works with non-Response return values."""

        @etag
        async def handler() -> dict[str, str]:
            return {"data": "test"}

        result = await handler()
        assert isinstance(result, dict)


class TestETagMatching:
    """Tests for the _etag_matches helper function."""

    def test_exact_match(self) -> None:
        """Verify exact ETag matching."""
        assert _etag_matches('W/"abc123"', 'W/"abc123"') is True

    def test_weak_etag_stripping(self) -> None:
        """Verify weak ETags are handled correctly."""
        assert _etag_matches('"abc123"', 'W/"abc123"') is True

    def test_no_match(self) -> None:
        """Verify non-matching ETags return False."""
        assert _etag_matches('W/"abc123"', 'W/"xyz789"') is False

    def test_star_wildcard(self) -> None:
        """Verify * wildcard matches anything."""
        assert _etag_matches("*", 'W/"abc123"') is True

    def test_multiple_etags_in_header(self) -> None:
        """Verify comma-separated ETag list is handled."""
        assert _etag_matches('W/"abc123", W/"xyz789"', 'W/"abc123"') is True

    def test_whitespace_handling(self) -> None:
        """Verify whitespace is handled correctly."""
        assert _etag_matches('  W/"abc123"  ', 'W/"abc123"') is True