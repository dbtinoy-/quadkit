"""HTTP client module for quadkit-http."""

from __future__ import annotations

from quadkit.http.client._streaming import StreamResponse
from quadkit.http.client.base_url_client import BaseURLHTTPClient, StreamContext
from quadkit.http.client.http_client import HTTPClient
from quadkit.http.pool import ConnectionPool

__all__ = [
    "BaseURLHTTPClient",
    "ConnectionPool",
    "HTTPClient",
    "StreamContext",
    "StreamResponse",
]
