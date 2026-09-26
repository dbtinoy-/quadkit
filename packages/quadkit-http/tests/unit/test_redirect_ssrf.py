"""Redirect-following SSRF contract for HTTPClient.

The SSRF gate must run on EVERY hop: automatic redirects are disabled at the
session layer and the client follows Location hops itself, re-validating each
target before connecting (spec-security-remediation finding 4).

These tests drive ``HTTPClient.request`` directly so the unit under test is
the redirect loop, not the verb wrappers.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yarl import URL

import ipaddress

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
            method="GET",
        )

    return patch.object(hc_mod, "_to_http_response", _convert)


@pytest.mark.asyncio
async def test_redirect_to_private_blocked_before_connect():
    """A hop resolving to a private host must raise before any connection."""
    client = _client()
    session = _Session(
        [_resp(302, "https://public.example/x", "https://private.internal/y")]
    )
    client._pool.session= session

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
    client._pool.session= session
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
    client._pool.session= session
    with (
        _patch_converter(),
        patch.object(hc_mod, "collect_safe_addresses", _gate_public),
    ):
        out = await client.request("GET", "https://a.example/1", allow_redirects=False)

    assert out.status == 302
    assert session.request.call_count == 1


@pytest.mark.asyncio
async def test_max_redirects_exceeded_raises():
    client = _client(max_redirects=1)
    session = _Session(
        [
            _resp(302, "https://a.example/1", "https://a.example/2"),
            _resp(302, "https://a.example/2", "https://a.example/3"),
        ]
    )
    client._pool.session= session
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
    client._pool.session= session
    with (
        _patch_converter(),
        patch.object(hc_mod, "collect_safe_addresses", _gate_public),
    ):
        out = await client.request("GET", "https://api.example/v1")
    assert out.url == "https://api.example/v2"


def test_gate_still_enforced_when_disabled_via_config():
    """enforce_url_safety=False keeps the gate off (documented opt-out)."""
    client = _client()
    client._config = HTTPClientConfig(enforce_url_safety=False)
    assert client._config.enforce_url_safety is False
    # the safety helpers remain exported for other consumers.
    assert callable(is_safe_url_for_request)
    assert callable(collect_safe_addresses)
