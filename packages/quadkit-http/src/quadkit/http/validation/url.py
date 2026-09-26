"""URL and hostname validation utilities for quadkit.http.

Validates URLs and hostnames. Raises :class:`~quadkit.http.exceptions.HTTPError`
on invalid input so callers get a well-typed infrastructure error.
"""

from __future__ import annotations

import re
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
    "validate_url",
]
