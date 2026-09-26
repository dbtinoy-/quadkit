"""URL helper utilities.

Pure functions for building and parsing URLs — no framework dependencies.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse


def build_url(
    base: str,
    path: str = "",
    params: dict[str, Any] | None = None,
) -> str:
    """Build a complete URL from base, path, and query parameters.

    Args:
        base: Base URL (e.g. ``"https://api.example.com"``).
        path: URL path to append (e.g. ``"/users/123"``).
        params: Optional query parameters; ``None`` values are omitted.

    Returns:
        Complete URL with path and encoded query string.

    Example:
        >>> build_url("https://api.example.com", "/users", {"page": 1})
        'https://api.example.com/users?page=1'
    """
    if base.endswith("/") and path.startswith("/"):
        url = base[:-1] + path
    elif not base.endswith("/") and not path.startswith("/") and path:
        url = base + "/" + path
    else:
        url = base + path

    if params:
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            url = f"{url}?{urlencode(filtered)}"

    return url


def parse_url_parts(url: str) -> dict[str, Any]:
    """Parse a URL into its component parts.

    Args:
        url: Full URL to parse.

    Returns:
        Dictionary with keys ``scheme``, ``host``, ``port``, ``path``,
        ``params``, ``fragment``.
    """
    parsed = urlparse(url)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port,
        "path": parsed.path,
        "params": parse_qs(parsed.query),
        "fragment": parsed.fragment,
    }


__all__ = ["build_url", "parse_url_parts"]
