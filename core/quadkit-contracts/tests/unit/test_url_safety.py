"""Tests for the shared SSRF URL-safety primitive (D1)."""

from __future__ import annotations

import ipaddress

import pytest

from quadkit.contracts.security import (
    HostResolver,
    is_safe_url_for_request,
    resolve_hostname,
)

PUBLIC_IP = ipaddress.ip_address("93.184.216.34")


def _public_resolver(
    hostname: str,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    return [PUBLIC_IP]


class TestSchemeAndStructure:
    def test_rejects_empty_url(self) -> None:
        assert is_safe_url_for_request("") is False

    def test_rejects_non_http_schemes(self) -> None:
        assert is_safe_url_for_request("ftp://example.com/x") is False
        assert is_safe_url_for_request("file:///etc/passwd") is False
        assert is_safe_url_for_request("data:text/plain,hi") is False
        assert is_safe_url_for_request("javascript:alert(1)") is False

    def test_rejects_missing_hostname(self) -> None:
        assert is_safe_url_for_request("https:///path") is False


class TestLiteralIpBlocklist:
    @pytest.mark.parametrize(
        "url",
        [
            "http://192.168.1.10/api",
            "http://10.0.0.1/api",
            "http://172.16.0.5/api",
            "http://127.0.0.1/api",
            "http://169.254.169.254/latest/meta-data/",
            "http://100.64.0.1/api",
        ],
    )
    def test_blocks_private_ipv4(self, url: str) -> None:
        assert is_safe_url_for_request(url) is False

    def test_blocks_ipv4_mapped_ipv6_private(self) -> None:
        assert is_safe_url_for_request("http://[::ffff:192.168.0.10]/api") is False

    def test_blocks_loopback_ipv6(self) -> None:
        assert is_safe_url_for_request("http://[::1]/api") is False

    def test_allows_public_ipv4(self) -> None:
        assert is_safe_url_for_request("http://93.184.216.34/api") is True

    def test_allows_public_ipv6(self) -> None:
        assert is_safe_url_for_request("http://[2606:4700:4700::1111]/") is True


class TestDnsResolution:
    def test_allows_hostname_resolving_to_public(self) -> None:
        assert (
            is_safe_url_for_request(
                "https://example.com/hook", resolver=_public_resolver
            )
            is True
        )

    def test_blocks_hostname_resolving_to_private(self) -> None:
        def resolver(hostname: str) -> list[ipaddress.IPv4Address]:
            return [ipaddress.ip_address("10.0.0.5")]

        assert (
            is_safe_url_for_request("https://evil.example/hook", resolver=resolver)
            is False
        )

    def test_blocks_hostname_with_any_private_addr(self) -> None:
        def resolver(
            hostname: str,
        ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
            return [PUBLIC_IP, ipaddress.ip_address("192.168.0.1")]

        assert (
            is_safe_url_for_request("https://split.example/", resolver=resolver)
            is False
        )

    def test_fails_closed_when_resolution_raises(self) -> None:
        def resolver(hostname: str) -> list[ipaddress.ip_address]:
            raise OSError("NXDOMAIN")

        assert (
            is_safe_url_for_request("https://nope.example/", resolver=resolver) is False
        )

    def test_fails_closed_when_resolution_returns_nothing(self) -> None:
        assert (
            is_safe_url_for_request("https://none.example/", resolver=lambda _: [])
            is False
        )


class TestResolverShape:
    def test_is_a_type_alias(self) -> None:
        # Compile-time only; assert it imports and is importable.
        assert callable(resolve_hostname)
        assert HostResolver is not None
