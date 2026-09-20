"""Unit tests for @cache_control and @etag decorators."""

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.testclient import TestClient

from quadkit.web.routing.caching import cache_control, etag


def make_request(headers: dict[str, str] | None = None) -> Request:
    """Build a minimal fake Starlette Request."""
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": raw_headers,
    }
    return Request(scope)


class TestCacheControl:
    """Tests for @cache_control decorator."""

    @pytest.mark.asyncio
    async def test_sets_cache_control_header_on_response(self):
        """@cache_control injects Cache-Control onto returned Response."""

        @cache_control(max_age=60, public=True)
        async def handler():
            return JSONResponse({"ok": True})

        response = await handler()
        assert "Cache-Control" in response.headers
        assert "max-age=60" in response.headers["Cache-Control"]
        assert "public" in response.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_no_store_directive(self):
        """no_store=True produces no-store directive."""

        @cache_control(no_store=True)
        async def handler():
            return JSONResponse({"ok": True})

        response = await handler()
        assert "no-store" in response.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_private_directive(self):
        """private=True produces private directive."""

        @cache_control(private=True, max_age=300)
        async def handler():
            return JSONResponse({"ok": True})

        response = await handler()
        cc = response.headers["Cache-Control"]
        assert "private" in cc
        assert "max-age=300" in cc

    @pytest.mark.asyncio
    async def test_immutable_directive(self):
        """immutable=True produces immutable directive."""

        @cache_control(max_age=31536000, immutable=True)
        async def handler():
            return JSONResponse({"ok": True})

        response = await handler()
        assert "immutable" in response.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_passthrough_for_non_response_return(self):
        """When handler returns non-Response (raw dict), it passes through unchanged."""

        @cache_control(max_age=60)
        async def handler():
            return {"data": "value"}

        result = await handler()
        # Should not crash; raw data passes through unchanged
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """Decorator preserves the original function name for introspection."""

        @cache_control(max_age=10)
        async def my_handler():
            return Response()

        assert my_handler.__name__ == "my_handler"

    @pytest.mark.asyncio
    async def test_stale_while_revalidate(self):
        """stale_while_revalidate is included in Cache-Control."""

        @cache_control(max_age=30, stale_while_revalidate=60)
        async def handler():
            return Response()

        response = await handler()
        cc = response.headers["Cache-Control"]
        assert "stale-while-revalidate=60" in cc

    def test_cache_control_attr_set(self):
        """Decorator stores the computed header value on the function."""

        @cache_control(max_age=120, public=True)
        async def handler():
            return Response()

        assert hasattr(handler, "__http_cache_control__")
        assert "max-age=120" in handler.__http_cache_control__


class TestEtag:
    """Tests for @etag decorator."""

    @pytest.mark.asyncio
    async def test_sets_etag_header(self):
        """@etag adds an ETag header to the response."""

        @etag
        async def handler():
            return JSONResponse({"data": "hello"})

        response = await handler()
        assert "ETag" in response.headers
        assert response.headers["ETag"].startswith('W/"')

    @pytest.mark.asyncio
    async def test_304_when_etag_matches(self):
        """Returns 304 Not Modified when If-None-Match matches ETag."""

        @etag
        async def handler(request: Request):
            return JSONResponse({"data": "hello"})

        # First request — get the ETag
        first = await handler(make_request())
        etag_value = first.headers["ETag"]

        # Second request — send the ETag back
        second = await handler(make_request({"If-None-Match": etag_value}))
        assert second.status_code == 304
        assert second.body == b""

    @pytest.mark.asyncio
    async def test_200_when_etag_does_not_match(self):
        """Returns 200 when If-None-Match does not match ETag."""

        @etag
        async def handler(request: Request):
            return JSONResponse({"data": "hello"})

        response = await handler(make_request({"If-None-Match": '"stale-etag"'}))
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_wildcard_if_none_match(self):
        """If-None-Match: * always triggers 304."""

        @etag
        async def handler(request: Request):
            return JSONResponse({"data": "anything"})

        response = await handler(make_request({"If-None-Match": "*"}))
        assert response.status_code == 304

    @pytest.mark.asyncio
    async def test_passthrough_for_non_response_return(self):
        """Raw data return values pass through unchanged."""

        @etag
        async def handler():
            return {"data": "value"}

        result = await handler()
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """Decorator preserves the original function name."""

        @etag
        async def my_handler():
            return Response()

        assert my_handler.__name__ == "my_handler"

    def test_etag_attr_set(self):
        """Decorator stores a marker attribute on the function."""

        @etag
        async def handler():
            return Response()

        assert getattr(handler, "__http_etag__", False) is True
