"""HTTP interceptor chains, provider wiring, and protocol conformance."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.http.config import ConnectionPoolConfig, HTTPClientConfig
from quadkit.http.constants import (
    CONTENT_TYPE_JSON,
    DEFAULT_ENCODING,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_TIMEOUT,
    GET,
    POST,
)
from quadkit.http.exceptions import (
    HTTPCircuitOpenError,
    HTTPClientError,
    HTTPConnectionError,
    HTTPInterceptorError,
    HTTPRetryExhaustedError,
    HTTPTimeoutError,
)
from quadkit.http.lib import (
    build_url,
    extract_json_type,
    format_timeout,
    merge_headers,
    parse_headers,
    parse_url_parts,
)
from quadkit.http.pool import ConnectionPool
from quadkit.http.types import RequestContext, ResponseContext
from quadkit.http.validation import (
    validate_host,
    validate_port,
    validate_positive_int,
    validate_timeout,
    validate_url,
)

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------



from http_module_test_support import _make_mock_retry_policy, _make_raw_response


class TestHTTPClientInterceptors:
    """Verify interceptors receive and can modify request/response."""

    @pytest.mark.asyncio
    async def test_request_interceptor_modifies_headers(self) -> None:
        from quadkit.http.client import HTTPClient

        class HeaderInjector:
            async def intercept_request(self, ctx: RequestContext) -> RequestContext:
                ctx.headers["x-injected"] = "yes"
                return ctx

            async def intercept_response(self, resp: object) -> object:
                return resp

        raw = _make_raw_response(status=200)
        retry_policy = _make_mock_retry_policy()
        client = HTTPClient(retry_policy=retry_policy, interceptors=[HeaderInjector()])

        captured_headers: dict[str, str] = {}

        async def fake_request(method: str, url: str, **kwargs: object) -> MagicMock:
            captured_headers.update(kwargs.get("headers", {}))  # type: ignore[arg-type]
            return raw

        client._pool = SimpleNamespace(  # type: ignore[assignment]
            session=SimpleNamespace(request=fake_request),
            pin_dns=lambda host, addrs: None,
        )
        await client.get("http://example.com/")
        assert captured_headers.get("x-injected") == "yes"

    @pytest.mark.asyncio
    async def test_response_interceptor_annotates_response(self) -> None:
        from quadkit.http.client import HTTPClient

        class Annotator:
            async def intercept_request(self, ctx: object) -> object:
                return ctx

            async def intercept_response(self, resp: object) -> object:
                resp.annotated = True
                return resp

        raw = _make_raw_response(status=200)
        retry_policy = _make_mock_retry_policy()
        client = HTTPClient(retry_policy=retry_policy, interceptors=[Annotator()])
        client._pool = SimpleNamespace(  # type: ignore[assignment]
            session=SimpleNamespace(request=AsyncMock(return_value=raw)),
            pin_dns=lambda host, addrs: None,
        )
        await client.get("http://example.com/")
        assert getattr(raw, "annotated", False) is True


# ---------------------------------------------------------------------------
# Interceptor chain ordering
# ---------------------------------------------------------------------------


class TestHTTPInterceptorChainOrder:
    """Verify that multiple interceptors are applied in registration order."""

    @pytest.mark.asyncio
    async def test_request_interceptors_applied_in_order(self) -> None:
        """Request interceptors run in the order they are passed to HTTPClient."""
        from quadkit.http.client import HTTPClient

        order: list[str] = []

        class First:
            async def intercept_request(self, ctx: RequestContext) -> RequestContext:
                order.append("first-req")
                ctx.headers["x-first"] = "1"
                return ctx

            async def intercept_response(self, resp: object) -> object:
                order.append("first-resp")
                return resp

        class Second:
            async def intercept_request(self, ctx: RequestContext) -> RequestContext:
                order.append("second-req")
                ctx.headers["x-second"] = "2"
                return ctx

            async def intercept_response(self, resp: object) -> object:
                order.append("second-resp")
                return resp

        raw = _make_raw_response(status=200)
        retry_policy = _make_mock_retry_policy()
        client = HTTPClient(
            retry_policy=retry_policy,
            interceptors=[First(), Second()],
        )
        captured: dict[str, str] = {}

        async def fake_request(method: str, url: str, **kwargs: object) -> MagicMock:
            captured.update(kwargs.get("headers", {}))  # type: ignore[arg-type]
            return raw

        client._pool = SimpleNamespace(  # type: ignore[assignment]
            session=SimpleNamespace(request=fake_request),
            pin_dns=lambda host, addrs: None,
        )
        await client.get("http://example.com/")

        # Request interceptors run first→second
        assert order.index("first-req") < order.index("second-req")
        # Response interceptors run first→second (same order, not reversed)
        assert order.index("first-resp") < order.index("second-resp")
        # Both headers were injected
        assert captured.get("x-first") == "1"
        assert captured.get("x-second") == "2"

    @pytest.mark.asyncio
    async def test_later_interceptor_can_see_earlier_header_mutation(self) -> None:
        """A downstream interceptor sees mutations made by earlier interceptors."""
        from quadkit.http.client import HTTPClient

        class Setter:
            async def intercept_request(self, ctx: RequestContext) -> RequestContext:
                ctx.headers["x-chain"] = "set"
                return ctx

            async def intercept_response(self, resp: object) -> object:
                return resp

        class Reader:
            def __init__(self) -> None:
                self.saw: str | None = None

            async def intercept_request(self, ctx: RequestContext) -> RequestContext:
                self.saw = ctx.headers.get("x-chain")
                return ctx

            async def intercept_response(self, resp: object) -> object:
                return resp

        reader = Reader()
        raw = _make_raw_response(status=200)
        retry_policy = _make_mock_retry_policy()
        client = HTTPClient(
            retry_policy=retry_policy,
            interceptors=[Setter(), reader],
        )
        client._pool = SimpleNamespace(  # type: ignore[assignment]
            session=SimpleNamespace(request=AsyncMock(return_value=raw)),
            pin_dns=lambda host, addrs: None,
        )
        await client.get("http://example.com/")
        assert reader.saw == "set"


# ---------------------------------------------------------------------------
# HTTPProvider (DI)
# ---------------------------------------------------------------------------


class TestHTTPProvider:
    @pytest.mark.asyncio
    async def test_get_client_before_boot_raises(self) -> None:
        from quadkit.http.di.provider import HTTPProvider

        provider = HTTPProvider()
        with pytest.raises(RuntimeError, match="not been booted"):
            provider._get_client()

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_before_boot(self) -> None:
        from quadkit.contracts.core import HealthStatus
        from quadkit.http.di.provider import HTTPProvider

        provider = HTTPProvider()
        result = await provider.health_check()
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_register_adds_singleton_bindings(self) -> None:
        from quadkit.contracts.web import HTTPClientProtocol
        from quadkit.http.client import HTTPClient
        from quadkit.http.di.provider import HTTPProvider

        provider = HTTPProvider()

        registered: dict[type, object] = {}

        class FakeRegistrar:
            def singleton(self, key: type, factory: object) -> None:
                registered[key] = factory

        await provider.register(FakeRegistrar())  # type: ignore[arg-type]
        assert HTTPClient in registered
        assert HTTPClientProtocol in registered

    @pytest.mark.asyncio
    async def test_boot_and_shutdown_lifecycle(self) -> None:
        from quadkit.contracts.core import HealthStatus
        from quadkit.http.di.provider import HTTPProvider

        provider = HTTPProvider()

        class FakeResolver:
            async def resolve(self, key: type) -> object:
                raise RuntimeError("not registered")

        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        result = await provider.health_check()
        assert result.status == HealthStatus.HEALTHY

        await provider.shutdown()
        result = await provider.health_check()
        assert result.status == HealthStatus.UNHEALTHY


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_http_client_satisfies_protocol(self) -> None:
        from quadkit.contracts.web import HTTPClientProtocol
        from quadkit.http.client import HTTPClient

        assert isinstance(HTTPClient(), HTTPClientProtocol)

    def test_connection_pool_is_importable_via_public_api(self) -> None:
        from quadkit.http.client import ConnectionPool as CP

        assert CP is ConnectionPool

    def test_lazy_api_exports_all_names(self) -> None:
        import quadkit.http as http_mod

        for name in [
            "HTTPClient",
            "HTTPProvider",
            "HTTPClientConfig",
            "ConnectionPoolConfig",
            "ConnectionPool",
            "HTTPClientError",
            "build_url",
            "validate_url",
            "RequestContext",
            "ResponseContext",
        ]:
            assert hasattr(http_mod, name), f"quadkit.http.client missing {name!r}"
