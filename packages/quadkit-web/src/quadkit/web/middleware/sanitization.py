"""Input sanitization middleware.

Strips dangerous characters and patterns from query parameters and path
parameters before they reach application code.  It does **not** inspect
request bodies — callers should validate/sanitize body payloads at the
service layer.

Usage::

    from quadkit.web.middleware.sanitization import InputSanitizationMiddleware

    app.add_middleware(InputSanitizationMiddleware)

Or via the WebProvider middleware stack by adding it to ``extra_middleware``.
"""

from __future__ import annotations

import re
from typing import Any
import urllib.parse

from quadkit.logging import get_logger

logger = get_logger(__name__)

# Patterns that are typically dangerous in query/path parameters.
_NULL_BYTES_RE = re.compile(r"\x00")

# Very basic XSS / script-injection check: tags and javascript: pseudo-URIs.
_SCRIPT_TAG_RE = re.compile(r"<\s*script", re.IGNORECASE)
_JS_URI_RE = re.compile(r"javascript\s*:", re.IGNORECASE)


def _sanitize_value(value: str) -> str:
    """Remove null bytes and flag obvious script-injection patterns.

    Args:
        value: Raw string value from a query or path parameter.

    Returns:
        Sanitized string with null bytes stripped.  Returns an empty
        string when an obvious injection pattern is detected and the
        request is not forwarded with that parameter intact.
    """
    # Strip null bytes unconditionally — they are never legitimate in URLs.
    value = _NULL_BYTES_RE.sub("", value)

    # Drop the entire value for obvious script injection.
    if _SCRIPT_TAG_RE.search(value) or _JS_URI_RE.search(value):
        logger.warning(
            "security.input_sanitization.blocked",
            reason="script_injection",
            value_prefix=value[:50],
        )
        return ""

    return value


class InputSanitizationMiddleware:
    """ASGI middleware that sanitizes query string parameters.

    Strips null bytes and rejects obvious script-injection patterns from
    query parameters before they reach request handlers.  Path parameters
    are not modified because they have been parsed and validated by the
    router before they hit middleware.

    This is a **defense-in-depth** measure, not a substitute for
    validation at the service layer.

    Args:
        app: The ASGI application to wrap.
        sanitize_query_params: Whether to sanitize query string values
            (default: ``True``).
    """

    def __init__(
        self,
        app: Any,
        sanitize_query_params: bool = True,
    ) -> None:
        self.app = app
        self.sanitize_query_params = sanitize_query_params

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or not self.sanitize_query_params:
            await self.app(scope, receive, send)
            return

        raw_query: bytes = scope.get("query_string", b"")
        if raw_query:
            sanitized_scope = dict(scope)
            sanitized_scope["query_string"] = self._sanitize_query(raw_query)
            await self.app(sanitized_scope, receive, send)
        else:
            await self.app(scope, receive, send)

    def _sanitize_query(self, raw: bytes) -> bytes:
        """Sanitize the raw query string bytes.

        Args:
            raw: Raw ``QUERY_STRING`` bytes from the ASGI scope.

        Returns:
            Sanitized query string bytes with dangerous values replaced.
        """
        try:
            decoded = raw.decode("utf-8", errors="replace")
        except (UnicodeDecodeError, AttributeError):
            return raw

        params = urllib.parse.parse_qsl(decoded, keep_blank_values=True)
        sanitized = [(k, _sanitize_value(v)) for k, v in params]
        return urllib.parse.urlencode(sanitized).encode("utf-8")
