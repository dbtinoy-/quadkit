"""Canonical HTTP constants shared across all Quadkit packages.

These constants represent well-known HTTP values that would otherwise be
duplicated in every package that speaks HTTP.  Import from here rather
than hard-coding strings in individual extension packages.

Example::

    from quadkit.contracts.web.http_constants import GET, CONTENT_TYPE_JSON
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# HTTP Methods
# ---------------------------------------------------------------------------

GET = "GET"
POST = "POST"
PUT = "PUT"
DELETE = "DELETE"
PATCH = "PATCH"
HEAD = "HEAD"
OPTIONS = "OPTIONS"

# ---------------------------------------------------------------------------
# Content-Type values
# ---------------------------------------------------------------------------

CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_FORM = "application/x-www-form-urlencoded"
CONTENT_TYPE_TEXT = "text/plain"
CONTENT_TYPE_HTML = "text/html"
CONTENT_TYPE_MULTIPART = "multipart/form-data"
CONTENT_TYPE_BYTES = "application/octet-stream"

# ---------------------------------------------------------------------------
# Common header names (lowercase per HTTP/2 standard)
# ---------------------------------------------------------------------------

HEADER_CONTENT_TYPE = "content-type"
HEADER_AUTHORIZATION = "authorization"
HEADER_ACCEPT = "accept"
HEADER_USER_AGENT = "user-agent"
HEADER_X_REQUEST_ID = "x-request-id"

# ---------------------------------------------------------------------------
# Default encoding
# ---------------------------------------------------------------------------

DEFAULT_ENCODING = "utf-8"

__all__ = [
    "CONTENT_TYPE_BYTES",
    "CONTENT_TYPE_FORM",
    "CONTENT_TYPE_HTML",
    "CONTENT_TYPE_JSON",
    "CONTENT_TYPE_MULTIPART",
    "CONTENT_TYPE_TEXT",
    "DEFAULT_ENCODING",
    "DELETE",
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
]
