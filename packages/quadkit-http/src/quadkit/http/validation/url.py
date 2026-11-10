"""URL and hostname validation utilities for quadkit.http.

Validates URLs and hostnames. Raises :class:`~quadkit.http.exceptions.HTTPError`
on invalid input so callers get a well-typed infrastructure error.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

from quadkit.http.exceptions import HTTPClientError

# Regex for valid RFC-1123 hostnames
_HOSTNAME_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$",
)

# Regex for IPv4 addresses
_IPV4_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
)

_BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".home.arpa",
)


def _assert_public_ip(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    host: str,
) -> None:
    """Reject loopback, private, link-local, multicast, unspecified, and reserved IPs."""
    mapped = getattr(addr, "ipv4_mapped", None)
    target = mapped if mapped is not None else addr
    if (
        target.is_loopback
        or target.is_private
        or target.is_link_local
        or target.is_multicast
        or target.is_unspecified
        or target.is_reserved
        or not target.is_global
    ):
        raise HTTPClientError(
            f"Outbound URL host {host!r} resolves to non-public address {addr}"
        )


def validate_public_url(
    url: str,
    *,
    resolve_dns: bool = True,
    fail_on_dns_error: bool = True,
) -> None:
    """Validate that ``url`` is an ``http``/``https`` URL targeting a public host.

    Protects outbound HTTP fetchers (RSS, webhooks, OpenGraph scrapers) against
    Server-Side Request Forgery (SSRF) targeting loopback, RFC1918/ULA private
    ranges, cloud metadata link-local addresses (``169.254.169.254``), and
    internal DNS suffixes.

    Args:
        url: Candidate outbound URL.
        resolve_dns: Resolve hostnames via ``socket.getaddrinfo`` and verify all
            returned addresses are globally routable.
        fail_on_dns_error: When ``True`` (default), raise ``HTTPClientError`` if
            DNS lookup fails; when ``False``, still validate any resolved IPs
            while allowing mocked/offline transport layers to handle resolution.

    Raises:
        HTTPClientError: When ``url`` is malformed, uses a non-HTTP(S) scheme,
            contains embedded credentials, or targets a non-public host/IP.
    """
    validate_url(url, require_scheme=True)
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise HTTPClientError(f"Unsupported URL scheme {parsed.scheme!r}")
    if parsed.username is not None or parsed.password is not None:
        raise HTTPClientError("URL must not contain embedded credentials")

    raw_host = parsed.hostname
    if not raw_host:
        raise HTTPClientError("URL must include a hostname")
    host = raw_host.rstrip(".").lower()
    if host == "localhost" or host.endswith(_BLOCKED_HOST_SUFFIXES):
        raise HTTPClientError(f"Outbound URL host {raw_host!r} is not permitted")

    try:
        ip_literal = ipaddress.ip_address(host)
    except ValueError:
        validate_host(host)
        if resolve_dns:
            port = parsed.port or (443 if scheme == "https" else 80)
            try:
                infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            except socket.gaierror as exc:
                if fail_on_dns_error:
                    raise HTTPClientError(
                        f"Unable to resolve outbound URL host {raw_host!r}: {exc}"
                    ) from exc
                return
            if not infos:
                if fail_on_dns_error:
                    raise HTTPClientError(
                        f"Outbound URL host {raw_host!r} returned no addresses"
                    )
                return
            for info in infos:
                sockaddr = info[4]
                resolved_ip = ipaddress.ip_address(str(sockaddr[0]).split("%")[0])
                _assert_public_ip(resolved_ip, host=raw_host)
    else:
        _assert_public_ip(ip_literal, host=raw_host)


def validate_url(url: str, require_scheme: bool = True) -> None:
    """Validate a URL string.

    Args:
        url: URL to validate.
        require_scheme: When ``True``, ``http``/``https`` scheme is required.

    Raises:
        HTTPError: If the URL is missing, malformed, or missing a required
            scheme.
    """
    if not url or not isinstance(url, str):
        raise HTTPClientError("URL must be a non-empty string")
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError) as exc:
        raise HTTPClientError(f"Invalid URL format: {exc}") from exc
    if require_scheme and not parsed.scheme:
        raise HTTPClientError("URL must include scheme (http or https)")
    if not parsed.netloc and not parsed.path:
        raise HTTPClientError("URL must include a hostname or path")


def validate_host(host: str) -> None:
    """Validate a hostname or IPv4 address.

    Args:
        host: Hostname or IP address to validate.

    Raises:
        HTTPError: If the host is empty or has an invalid format.
    """
    if not host or not isinstance(host, str):
        raise HTTPClientError("Host must be a non-empty string")
    if _IPV4_PATTERN.match(host):
        return
    if not _HOSTNAME_PATTERN.match(host):
        raise HTTPClientError(f"Invalid hostname or IP address: {host!r}")


__all__ = [
    "validate_host",
    "validate_public_url",
    "validate_url",
]
