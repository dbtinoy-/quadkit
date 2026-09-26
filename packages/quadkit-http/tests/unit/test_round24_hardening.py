"""Round-24 hardening pins for quadkit-http (+ quadkit-contracts url safety).

Covers:
- collect_safe_addresses: literal public/private IPs, DNS validation via
  injected resolver, fail-closed behaviour, is_safe_url_for_request parity
- PinnedThreadedResolver: pinned hosts resolve ONLY to the pinned set
- ConnectionPool.pin_dns: pins flow into the connector's resolver
- HTTPClient._assert_url_safe: pins DNS hosts after validation, rejects
  unsafe URLs, stays inert when safety enforcement is off
"""

from __future__ import annotations

import asyncio
import ipaddress
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

PUBLIC_IP = ipaddress.ip_address("93.184.216.34")
PRIVATE_IP = ipaddress.ip_address("127.0.0.1")


# ────────────────────────────────────────────────────────────
# contracts.security.collect_safe_addresses
# ────────────────────────────────────────────────────────────


class TestCollectSafeAddresses:
    def test_literal_public_ip(self) -> None:
        from quadkit.contracts.security import collect_safe_addresses

        assert collect_safe_addresses("http://93.184.216.34/x") == [PUBLIC_IP]

    def test_literal_private_ip_rejected(self) -> None:
        from quadkit.contracts.security import collect_safe_addresses

        with pytest.raises(ValueError, match="private/reserved"):
            collect_safe_addresses("http://127.0.0.1/x")

    def test_dns_all_public(self) -> None:
        from quadkit.contracts.security import collect_safe_addresses

        resolver = lambda host: [PUBLIC_IP]  # noqa: E731
        assert collect_safe_addresses("https://a.example/x", resolver=resolver) == [
            PUBLIC_IP
        ]

    def test_dns_mixed_rejected(self) -> None:
        from quadkit.contracts.security import collect_safe_addresses

        resolver = lambda host: [PUBLIC_IP, PRIVATE_IP]  # noqa: E731
        with pytest.raises(ValueError, match="private/reserved"):
            collect_safe_addresses("https://a.example/x", resolver=resolver)

    def test_dns_unresolvable_rejected(self) -> None:
        from quadkit.contracts.security import collect_safe_addresses

        def _boom(host: str):
            raise OSError("no such host")

        with pytest.raises(ValueError, match="could not be resolved"):
            collect_safe_addresses("https://a.example/x", resolver=_boom)

    def test_dns_empty_resolution_rejected(self) -> None:
        from quadkit.contracts.security import collect_safe_addresses

        with pytest.raises(ValueError, match="no addresses"):
            collect_safe_addresses("https://a.example/x", resolver=lambda h: [])

    def test_bad_scheme_rejected(self) -> None:
        from quadkit.contracts.security import collect_safe_addresses

        with pytest.raises(ValueError, match="scheme"):
            collect_safe_addresses("ftp://a.example/x")

    def test_bool_facade_parity(self) -> None:
        from quadkit.contracts.security import (
            collect_safe_addresses,
            is_safe_url_for_request,
        )

        cases = [
            "http://93.184.216.34/x",
            "http://127.0.0.1/x",
            "ftp://a.example/x",
            "https://a.example/x",
        ]
        for url in cases:
            resolver = lambda host: [PUBLIC_IP]  # noqa: E731
            expected = False
            try:
                collect_safe_addresses(url, resolver=resolver)
                expected = True
            except ValueError:
                pass
            assert is_safe_url_for_request(url, resolver=resolver) is expected


# ────────────────────────────────────────────────────────────
# Pinned resolver
# ────────────────────────────────────────────────────────────


class TestPinnedResolver:
    @pytest.mark.asyncio
    async def test_pinned_host_resolves_only_to_pins(self) -> None:
        from quadkit.http.pool.connection_pool import _PinnedThreadedResolver

        resolver = _PinnedThreadedResolver()
        resolver.pin("a.example", [PUBLIC_IP])

        results = await resolver.resolve("a.example", port=443)
        assert [r["host"] for r in results] == ["93.184.216.34"]
        assert all(r["port"] == 443 for r in results)
        assert all(r["hostname"] == "a.example" for r in results)

    @pytest.mark.asyncio
    async def test_pin_replacement(self) -> None:
        from quadkit.http.pool.connection_pool import _PinnedThreadedResolver

        resolver = _PinnedThreadedResolver()
        resolver.pin("a.example", [PUBLIC_IP])
        resolver.pin("a.example", [ipaddress.ip_address("203.0.113.9")])

        results = await resolver.resolve("a.example", port=443)
        assert [r["host"] for r in results] == ["203.0.113.9"]

    @pytest.mark.asyncio
    async def test_ipv6_pin_family(self) -> None:
        import socket

        from quadkit.http.pool.connection_pool import _PinnedThreadedResolver

        resolver = _PinnedThreadedResolver()
        resolver.pin("v6.example", [ipaddress.ip_address("2001:db8::1")])
        results = await resolver.resolve("v6.example", port=443)
        assert results[0]["family"] == socket.AF_INET6


class TestPoolPinDns:
    def test_pin_dns_buffers_before_start(self) -> None:
        """pin_dns before start() must not fail (no event loop yet) and the
        pin must be retained for application at start()."""
        from quadkit.http.pool.connection_pool import ConnectionPool

        pool = ConnectionPool()
        pool.pin_dns("a.example", [PUBLIC_IP])
        assert pool._dns_pins["a.example"] == (PUBLIC_IP,)  # noqa: SLF001
        assert pool._pinned_resolver is None  # created lazily in start()

    def test_pool_connector_uses_pinned_resolver(self) -> None:
        """start() must wire the pinned resolver into the TCPConnector so
        connects actually use the validated addresses."""
        import inspect

        from quadkit.http.pool.connection_pool import ConnectionPool

        source = inspect.getsource(ConnectionPool.start)
        assert "resolver=self._pinned_resolver" in source

    @pytest.mark.asyncio
    async def test_start_applies_buffered_pins(self) -> None:
        from quadkit.http.pool.connection_pool import ConnectionPool

        pool = ConnectionPool()
        pool.pin_dns("a.example", [PUBLIC_IP])
        await pool.start()
        try:
            assert pool._pinned_resolver is not None  # noqa: SLF001
            results = await pool._pinned_resolver.resolve("a.example", port=443)
            assert [r["host"] for r in results] == ["93.184.216.34"]
        finally:
            await pool.stop()


# ────────────────────────────────────────────────────────────
# HTTPClient._assert_url_safe pinning
# ────────────────────────────────────────────────────────────


def _bare_client(enforce: bool = True):
    from quadkit.http.client.http_client import HTTPClient
    from quadkit.http.config import HTTPClientConfig

    client = HTTPClient.__new__(HTTPClient)
    client._config = HTTPClientConfig(enforce_url_safety=enforce)
    client._pool = MagicMock()
    return client


class TestAssertUrlSafePinning:
    @pytest.mark.asyncio
    async def test_dns_host_pinned_after_validation(self) -> None:
        client = _bare_client()
        with patch(
            "quadkit.http.client.http_client.collect_safe_addresses",
            return_value=[PUBLIC_IP],
        ):
            await client._assert_url_safe("https://a.example/path")  # noqa: SLF001

        client._pool.pin_dns.assert_called_once_with("a.example", [PUBLIC_IP])

    @pytest.mark.asyncio
    async def test_literal_ip_not_pinned(self) -> None:
        client = _bare_client()
        with patch(
            "quadkit.http.client.http_client.collect_safe_addresses",
            return_value=[PUBLIC_IP],
        ):
            await client._assert_url_safe("http://93.184.216.34/path")  # noqa: SLF001

        client._pool.pin_dns.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsafe_url_rejected_without_pin(self) -> None:
        from quadkit.http.exceptions import HTTPUnsafeURLError

        client = _bare_client()

        def _bad(_url: str):
            raise ValueError("resolves to private address")

        with patch(
            "quadkit.http.client.http_client.collect_safe_addresses", _bad
        ):
            with pytest.raises(HTTPUnsafeURLError):
                await client._assert_url_safe("https://a.example/path")  # noqa: SLF001

        client._pool.pin_dns.assert_not_called()

    @pytest.mark.asyncio
    async def test_enforcement_off_is_inert(self) -> None:
        client = _bare_client(enforce=False)
        with patch(
            "quadkit.http.client.http_client.collect_safe_addresses",
            side_effect=AssertionError("gate must not run when disabled"),
        ):
            await client._assert_url_safe("https://a.example/path")  # noqa: SLF001
        client._pool.pin_dns.assert_not_called()
