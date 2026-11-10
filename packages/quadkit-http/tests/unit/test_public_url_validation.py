"""Unit tests for SSRF-safe ``validate_public_url`` in ``quadkit.http``."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from quadkit.http import HTTPClientError, validate_public_url


@pytest.mark.parametrize(
    "blocked_url",
    [
        "http://localhost/feed.xml",
        "http://api.internal/rss",
        "http://printer.local/feed",
        "http://127.0.0.1:8000/health",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/private",
        "http://172.16.4.2/private",
        "http://192.168.1.10/admin",
        "http://0.0.0.0:5432/",
        "http://[::1]:6379/",
        "file:///etc/passwd",
        "ftp://93.184.216.34/pub",
        "https://user:secret@93.184.216.34/feed",
    ],
)
def test_validate_public_url_rejects_ssrf_targets(blocked_url: str) -> None:
    """Loopback, private, link-local metadata, non-HTTP schemes, and creds fail."""
    with pytest.raises(HTTPClientError):
        validate_public_url(blocked_url, resolve_dns=False)


def test_validate_public_url_accepts_global_ip_and_public_dns() -> None:
    """Global public IPv4 literals and public A-records pass validation."""
    validate_public_url("https://93.184.216.34/rss.xml", resolve_dns=False)

    fake_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    ]
    with patch(
        "quadkit.http.validation.url.socket.getaddrinfo", return_value=fake_addrinfo
    ):
        validate_public_url("https://feeds.example.org/pets.xml", resolve_dns=True)


def test_validate_public_url_blocks_dns_rebinding_to_private_ip() -> None:
    """Hostnames resolving to private or metadata IPs are rejected."""
    rebinding_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))
    ]
    with (
        patch(
            "quadkit.http.validation.url.socket.getaddrinfo",
            return_value=rebinding_addrinfo,
        ),
        pytest.raises(HTTPClientError),
    ):
        validate_public_url("http://rebind.attacker.example/feed.xml", resolve_dns=True)
