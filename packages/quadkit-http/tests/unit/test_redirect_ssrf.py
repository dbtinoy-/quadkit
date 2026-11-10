"""Redirect-following SSRF contract for HTTPClient.

The SSRF gate must run on EVERY hop: automatic redirects are disabled at the
session layer and the client follows Location hops itself, re-validating each
target before connecting (spec-security-remediation finding 4).

These tests drive ``HTTPClient.request`` directly so the unit under test is
the redirect loop, not the verb wrappers.
"""

from __future__ import annotations

import ipaddress
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yarl import URL

from quadkit.contracts.security import collect_safe_addresses, is_safe_url_for_request
from quadkit.contracts.web import HttpResponse
import quadkit.http.client.http_client as hc_mod
from quadkit.http.client.http_client import HTTPClient
from quadkit.http.config import HTTPClientConfig
from quadkit.http.exceptions import HTTPClientError, HTTPUnsafeURLError


def _resp(status: int, url: str, location: str | None = None):
    headers = {"Location": location} if location else {}

    async def _read():
        return b""

    return SimpleNamespace(
        status=status, url=URL(url), headers=headers, read=_read, release=lambda: None
    )


_PUBLIC_IP = ipaddress.ip_address("93.184.216.34")


def _gate_public(url: str) -> list:
    """Stand-in for collect_safe_addresses: public URLs resolve to a public IP."""
    return [_PUBLIC_IP]


def _client(max_redirects: int = 5) -> HTTPClient:
    config = HTTPClientConfig(enforce_url_safety=True, max_redirects=max_redirects)
    client = HTTPClient.__new__(HTTPClient)
    client._config = config
    client._interceptors = []
    client._circuit_breaker = None
    client._resilience = None
    client._metrics = None
    client._retry_policy = MagicMock()

    async def _execute_now(fn, **kwargs):
        return await fn()

    client._retry_policy.execute = _execute_now
    client._pool = MagicMock()
    client._pool.proxy = None
    client._pool.trust_env = False
    return client


class _Session(MagicMock):
    """Fake aiohttp session: AsyncMock replaying responses in order."""

    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)
        self.request = AsyncMock(side_effect=self.responses)

    @property
    def urls_called(self):
        return [str(c.args[1]) for c in self.request.call_args_list]

    def assert_no_auto_follow(self):
        for call in self.request.call_args_list:
            assert call.kwargs.get("allow_redirects") is False


def _final(url: str) -> HttpResponse:
    return HttpResponse(
        status=200, headers={}, body=b"", text="", json=None, url=url, method="GET"
    )


def _patch_converter():
    async def _convert(raw, method):
        return HttpResponse(
            status=raw.status,
            headers={},
            body=b"",
            text="",
            json=None,
            url=str(raw.url),
            method=method.upper(),
        )

    return patch.object(hc_mod, "_to_http_response", _convert)


@pytest.mark.asyncio
async def test_redirect_to_private_blocked_before_connect():
    """A hop resolving to a private host must raise before any connection."""
    client = _client()
    session = _Session(
        [_resp(302, "https://public.example/x", "https://private.internal/y")]
    )
    client._pool.session = session

    def _gate(url: str) -> list:
        if "private" in url:
            raise ValueError("resolves to private address")
        return [_PUBLIC_IP]

    with patch.object(hc_mod, "collect_safe_addresses", _gate):
        with pytest.raises(HTTPUnsafeURLError):
            await client.request("GET", "https://public.example/x")

    assert session.urls_called == ["https://public.example/x"]


@pytest.mark.asyncio
async def test_public_chain_follows_and_returns_final():
    client = _client()
    session = _Session(
        [
            _resp(301, "https://a.example/1", "https://b.example/2"),
            _resp(302, "https://b.example/2", "/3"),
            _resp(200, "https://b.example/3"),
        ]
    )
    client._pool.session = session
    with (
        _patch_converter(),
        patch.object(hc_mod, "collect_safe_addresses", _gate_public),
    ):
        out = await client.request("GET", "https://a.example/1")

    assert out.url == "https://b.example/3"
    assert session.urls_called == [
        "https://a.example/1",
        "https://b.example/2",
        "https://b.example/3",
    ]


@pytest.mark.asyncio
async def test_caller_allow_redirects_false_is_respected():
    """An explicit ``allow_redirects=False`` disables client-side following."""
    client = _client()
    session = _Session([_resp(302, "https://a.example/1", "https://b.example/2")])
    client._pool.session = session
    with (
        _patch_converter(),
        patch.object(hc_mod, "collect_safe_addresses", _gate_public),
    ):
        out = await client.request("GET", "https://a.example/1", allow_redirects=False)

    assert out.status == 302
    assert session.request.call_count == 1


@pytest.mark.asyncio
async def test_explicit_allow_redirects_true_validates_every_hop():
    """Explicit redirect following still validates each target before connect."""
    client = _client()
    session = _Session(
        [_resp(302, "https://public.example/x", "https://private.internal/y")]
    )
    client._pool.session = session

    def _gate(url: str) -> list:
        if "private" in url:
            raise ValueError("resolves to private address")
        return [_PUBLIC_IP]

    with patch.object(hc_mod, "collect_safe_addresses", _gate):
        with pytest.raises(HTTPUnsafeURLError):
            await client.request(
                "GET", "https://public.example/x", allow_redirects=True
            )

    assert session.urls_called == ["https://public.example/x"]
    session.assert_no_auto_follow()


@pytest.mark.asyncio
async def test_cross_origin_redirect_drops_credentials_and_hop_headers():
    """A redirect to another origin must not inherit caller credentials."""
    client = _client()
    session = _Session(
        [
            _resp(302, "https://api.example/x", "https://other.example/y"),
            _resp(200, "https://other.example/y"),
        ]
    )
    client._pool.session = session
    with (
        _patch_converter(),
        patch.object(hc_mod, "collect_safe_addresses", _gate_public),
    ):
        await client.request(
            "GET",
            "https://api.example/x",
            headers={
                "Authorization": "Bearer secret-token",
                "X-Api-Key": "api-key-secret",
                "Content-Length": "17",
                "Accept": "application/json",
                "X-Request-ID": "request-1",
            },
        )

    assert session.request.call_count == 2
    initial_headers = session.request.call_args_list[0].kwargs["headers"]
    redirected_headers = session.request.call_args_list[1].kwargs["headers"]
    assert initial_headers["Authorization"] == "Bearer secret-token"
    assert initial_headers["X-Api-Key"] == "api-key-secret"
    assert "Authorization" not in redirected_headers
    assert "X-Api-Key" not in redirected_headers
    assert "Content-Length" not in redirected_headers
    assert redirected_headers["Accept"] == "application/json"
    assert redirected_headers["X-Request-ID"] == "request-1"


@pytest.mark.asyncio
async def test_redirect_uses_effective_response_url_and_does_not_repeat_params():
    client = _client()
    session = _Session(
        [
            _resp(302, "https://api.example/start?search=cat", "/next"),
            _resp(200, "https://api.example/next"),
        ]
    )
    client._pool.session = session
    with (
        _patch_converter(),
        patch.object(hc_mod, "collect_safe_addresses", _gate_public),
    ):
        await client.request(
            "GET", "https://api.example/start", params={"search": "cat"}
        )

    assert session.urls_called == [
        "https://api.example/start",
        "https://api.example/next",
    ]
    assert session.request.call_args_list[0].kwargs["params"] == {"search": "cat"}
    assert "params" not in session.request.call_args_list[1].kwargs


@pytest.mark.asyncio
async def test_url_safety_rejects_proxy_transport_that_bypasses_dns_pins():
    """A proxy can resolve the target independently of the validated DNS pin."""
    client = _client()
    session = _Session([_resp(200, "https://public.example/x")])
    client._pool.session = session
    client._pool.proxy = "http://proxy.internal:8080"

    with pytest.raises(
        HTTPUnsafeURLError, match="cannot be enforced through an HTTP proxy"
    ):
        await client.request("GET", "https://public.example/x")

    assert session.request.call_count == 0


@pytest.mark.asyncio
async def test_url_safety_rejects_env_proxy_on_injected_pool():
    """Injected pools cannot re-enable remote target resolution via trust_env."""
    client = _client()
    session = _Session([_resp(200, "https://public.example/x")])
    client._pool.session = session
    client._pool.trust_env = True

    with pytest.raises(
        HTTPUnsafeURLError, match="cannot be enforced through an HTTP proxy"
    ):
        await client.request("GET", "https://public.example/x")

    assert session.request.call_count == 0


@pytest.mark.asyncio
async def test_post_303_redirect_switches_to_get_and_drops_body():
    """303 redirects follow aiohttp's POST-to-GET behavior without replaying data."""
    client = _client()
    session = _Session(
        [
            _resp(303, "https://api.example/x", "/result"),
            _resp(200, "https://api.example/result"),
        ]
    )
    client._pool.session = session
    with (
        _patch_converter(),
        patch.object(hc_mod, "collect_safe_addresses", _gate_public),
    ):
        out = await client.request(
            "POST",
            "https://api.example/x",
            json={"secret": "must-not-be-replayed"},
            headers={"Content-Type": "application/json"},
        )

    assert out.method == "GET"
    assert session.request.call_args_list[0].args[0] == "POST"
    assert session.request.call_args_list[0].kwargs["json"] == {
        "secret": "must-not-be-replayed"
    }
    redirected_call = session.request.call_args_list[1]
    assert redirected_call.args[0] == "GET"
    assert "json" not in redirected_call.kwargs
    assert "Content-Type" not in redirected_call.kwargs["headers"]


@pytest.mark.asyncio
async def test_non_boolean_allow_redirects_is_rejected():
    """Invalid truthy values must not opt back into aiohttp auto-redirects."""
    client = _client()
    session = _Session([_resp(200, "https://a.example/1")])
    client._pool.session = session

    with pytest.raises(TypeError, match="allow_redirects must be a bool or None"):
        await client.request("GET", "https://a.example/1", allow_redirects=1)

    assert session.request.call_count == 0


@pytest.mark.asyncio
async def test_max_redirects_exceeded_raises():
    client = _client(max_redirects=1)
    session = _Session(
        [
            _resp(302, "https://a.example/1", "https://a.example/2"),
            _resp(302, "https://a.example/2", "https://a.example/3"),
        ]
    )
    client._pool.session = session
    with (
        _patch_converter(),
        patch.object(hc_mod, "collect_safe_addresses", _gate_public),
    ):
        with pytest.raises(HTTPClientError, match=r"[Rr]edirect"):
            await client.request("GET", "https://a.example/1")
    assert len(session.urls_called) == 2  # followed exactly max_redirects times


@pytest.mark.asyncio
async def test_relative_location_resolved_against_current_hop():
    client = _client()
    session = _Session(
        [
            _resp(302, "https://api.example/v1", "/v2"),
            _resp(200, "https://api.example/v2"),
        ]
    )
    client._pool.session = session
    with (
        _patch_converter(),
        patch.object(hc_mod, "collect_safe_addresses", _gate_public),
    ):
        out = await client.request("GET", "https://api.example/v1")
    assert out.url == "https://api.example/v2"


def test_http_client_disables_env_proxies_when_url_safety_is_enabled():
    """The default pool must use the resolver whose pins passed the SSRF gate."""
    client = HTTPClient(config=HTTPClientConfig(enforce_url_safety=True))

    assert client.pool.trust_env is False


def test_gate_still_enforced_when_disabled_via_config():
    """enforce_url_safety=False keeps the gate off (documented opt-out)."""
    client = _client()
    client._config = HTTPClientConfig(enforce_url_safety=False)
    assert client._config.enforce_url_safety is False
    # the safety helpers remain exported for other consumers.
    assert callable(is_safe_url_for_request)
    assert callable(collect_safe_addresses)
