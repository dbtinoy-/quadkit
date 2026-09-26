"""HTTP client constants for the quadkit.http module.

Shared HTTP values (methods, content-types, header names, encoding) are
imported from ``quadkit.contracts.web.constants`` and re-exported here
for backward compatibility.  Only connection-pool defaults live in this
module.
"""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit-http")
except ImportError:
    __version__ = "0.0.0"

ENV_PREFIX: str = "QK_HTTP__"
"""Environment variable prefix for HTTP configuration."""

ENV_NESTED_DELIMITER: str = "__"
"""Delimiter for nested env var keys (e.g. QK_HTTP__POOL__TIMEOUT)."""

# Re-export shared constants from contracts so callers that import from
# quadkit.http.constants continue to work unchanged.
from quadkit.contracts.web.http_constants import (
    CONTENT_TYPE_BYTES,
    CONTENT_TYPE_FORM,
    CONTENT_TYPE_HTML,
    CONTENT_TYPE_JSON,
    CONTENT_TYPE_MULTIPART,
    CONTENT_TYPE_TEXT,
    DEFAULT_ENCODING,
    DELETE,
    GET,
    HEAD,
    HEADER_ACCEPT,
    HEADER_AUTHORIZATION,
    HEADER_CONTENT_TYPE,
    HEADER_USER_AGENT,
    HEADER_X_REQUEST_ID,
    OPTIONS,
    PATCH,
    POST,
    PUT,
)

# Default connection pool settings (http-specific, not in contracts)
DEFAULT_MAX_CONNECTIONS = 10
DEFAULT_MAX_KEEPALIVE_CONNECTIONS = 5
DEFAULT_MAX_CONNECTIONS_PER_HOST = 10
DEFAULT_TIMEOUT = 30.0
DEFAULT_TTL_DNS_CACHE = 300

__all__ = [
    "CONTENT_TYPE_BYTES",
    "CONTENT_TYPE_FORM",
    "CONTENT_TYPE_HTML",
    "CONTENT_TYPE_JSON",
    "CONTENT_TYPE_MULTIPART",
    "CONTENT_TYPE_TEXT",
    "DEFAULT_ENCODING",
    "DEFAULT_MAX_CONNECTIONS",
    "DEFAULT_MAX_CONNECTIONS_PER_HOST",
    "DEFAULT_MAX_KEEPALIVE_CONNECTIONS",
    "DEFAULT_TIMEOUT",
    "DEFAULT_TTL_DNS_CACHE",
    "DELETE",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "GET",
    "HEAD",
    "HEADER_ACCEPT",
    "HEADER_AUTHORIZATION",
    "HEADER_CONTENT_TYPE",
    "HEADER_USER_AGENT",
    "HEADER_X_REQUEST_ID",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
    "__version__",
]
