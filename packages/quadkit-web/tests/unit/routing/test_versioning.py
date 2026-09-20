"""Tests for routing/versioning.py — VersionExtractor, VersioningMiddleware, version decorator."""

from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from quadkit.web.routing.versioning import (
    VersionExtractor,
    VersioningConfig,
    VersioningMiddleware,
    VersioningStrategy,
    get_version,
    version,
)


def _make_request(
    path: str = "/",
    headers: dict[str, str] | None = None,
    query_params: str = "",
) -> Request:
    scope = {
        "type": "http",
        "path": path,
        "query_string": query_params.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "method": "GET",
    }
    return Request(scope)


class TestVersioningStrategy:
    def test_strategy_values(self) -> None:
        assert VersioningStrategy.URI == "uri"
        assert VersioningStrategy.HEADER == "header"
        assert VersioningStrategy.MEDIA_TYPE == "media_type"
        assert VersioningStrategy.QUERY == "query"


class TestVersioningConfig:
    def test_defaults(self) -> None:
        cfg = VersioningConfig()
        assert cfg.strategy == VersioningStrategy.URI
        assert cfg.header_name == "X-API-Version"
        assert cfg.default_version == "1"
        assert cfg.uri_prefix == "v"


class TestVersionExtractorHeader:
    def test_extracts_version_from_header(self) -> None:
        cfg = VersioningConfig(strategy=VersioningStrategy.HEADER)
        extractor = VersionExtractor(cfg)
        req = _make_request(headers={"x-api-version": "2"})
        assert extractor.extract(req) == "2"

    def test_uses_default_when_header_missing(self) -> None:
        cfg = VersioningConfig(strategy=VersioningStrategy.HEADER, default_version="1")
        extractor = VersionExtractor(cfg)
        req = _make_request()
        assert extractor.extract(req) == "1"


class TestVersionExtractorURI:
    def test_extracts_version_from_uri(self) -> None:
        cfg = VersioningConfig(strategy=VersioningStrategy.URI)
        extractor = VersionExtractor(cfg)
        req = _make_request(path="/v2/users")
        assert extractor.extract(req) == "2"

    def test_uses_default_when_not_in_uri(self) -> None:
        cfg = VersioningConfig(strategy=VersioningStrategy.URI, default_version="1")
        extractor = VersionExtractor(cfg)
        req = _make_request(path="/api/users")
        assert extractor.extract(req) == "1"


class TestVersionExtractorMediaType:
    def test_extracts_version_from_accept_header(self) -> None:
        # The parser splits by "." and looks for parts like "v3" where v+digits are present
        # Format: application/vnd.api.v3.json (dots, not +suffix)
        cfg = VersioningConfig(strategy=VersioningStrategy.MEDIA_TYPE)
        extractor = VersionExtractor(cfg)
        req = _make_request(headers={"accept": "application/vnd.api.v3.json"})
        assert extractor.extract(req) == "3"

    def test_uses_default_when_not_in_accept(self) -> None:
        cfg = VersioningConfig(strategy=VersioningStrategy.MEDIA_TYPE, default_version="1")
        extractor = VersionExtractor(cfg)
        req = _make_request(headers={"accept": "application/json"})
        assert extractor.extract(req) == "1"


class TestVersionExtractorQuery:
    def test_extracts_version_from_query(self) -> None:
        cfg = VersioningConfig(strategy=VersioningStrategy.QUERY)
        extractor = VersionExtractor(cfg)
        req = _make_request(query_params="api_version=3")
        assert extractor.extract(req) == "3"

    def test_uses_default_when_query_param_missing(self) -> None:
        cfg = VersioningConfig(strategy=VersioningStrategy.QUERY, default_version="1")
        extractor = VersionExtractor(cfg)
        req = _make_request()
        assert extractor.extract(req) == "1"


class TestVersionDecorator:
    def test_sets_api_version_attribute(self) -> None:
        @version("2")
        class MyController:
            pass

        assert MyController.__api_version__ == "2"

    def test_returns_same_class(self) -> None:
        class MyController:
            pass

        result = version("1")(MyController)
        assert result is MyController


class TestVersioningMiddleware:
    @pytest.mark.asyncio
    async def test_sets_api_version_in_state(self) -> None:
        cfg = VersioningConfig(strategy=VersioningStrategy.HEADER)
        mw = VersioningMiddleware(cfg)

        state = {}

        async def call_next(req: Request) -> PlainTextResponse:
            state["version"] = req.state.api_version
            return PlainTextResponse("ok")

        req = _make_request(headers={"x-api-version": "5"})
        await mw(req, call_next)
        assert state["version"] == "5"

    @pytest.mark.asyncio
    async def test_returns_response_from_call_next(self) -> None:
        cfg = VersioningConfig()
        mw = VersioningMiddleware(cfg)

        async def call_next(req: Request) -> PlainTextResponse:
            return PlainTextResponse("response_body")

        req = _make_request()
        response = await mw(req, call_next)
        assert response.status_code == 200


class TestGetVersion:
    def test_returns_version_from_state(self) -> None:
        req = _make_request()
        req.state.api_version = "3"
        assert get_version(req) == "3"

    def test_defaults_to_1_when_not_set(self) -> None:
        req = _make_request()
        assert get_version(req) == "1"


class TestDeprecationHeaderWiring:
    """`@api_version(deprecated=True)` must emit RFC-8594-style headers.

    The decorator stored the metadata but no routing layer consumer existed —
    the promised ``Deprecation``/``Sunset`` headers were never sent. The
    wiring (with_deprecation_headers + manager hook) pins the contract here.
    """

    @pytest.mark.asyncio
    async def test_wrapper_sets_headers(self) -> None:
        from quadkit.web.routing.versioning import (
            ApiVersionMetadata,
            with_deprecation_headers,
        )

        async def endpoint(request):  # pragma: no cover - trivial stub
            return PlainTextResponse("ok")

        wrapped = with_deprecation_headers(
            endpoint, ApiVersionMetadata(version=1, deprecated=True, sunset="2030-01-01")
        )
        response = await wrapped(_make_request())

        assert response.headers["Deprecation"] == "true"
        assert response.headers["Sunset"] == "2030-01-01"

    @pytest.mark.asyncio
    async def test_wrapper_without_sunset_omits_header(self) -> None:
        from quadkit.web.routing.versioning import (
            ApiVersionMetadata,
            with_deprecation_headers,
        )

        async def endpoint(request):
            return PlainTextResponse("ok")

        wrapped = with_deprecation_headers(
            endpoint, ApiVersionMetadata(version=1, deprecated=True)
        )
        response = await wrapped(_make_request())

        assert response.headers["Deprecation"] == "true"
        assert "Sunset" not in response.headers
