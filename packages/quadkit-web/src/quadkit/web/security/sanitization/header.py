"""HTTP header sanitization helpers.

Prevents CRLF injection attacks in HTTP response headers.
This is HTTP-specific sanitization; transport-agnostic sanitizers
(HTML, URL, filename) live in ``quadkit.security.sanitization``.
"""

from __future__ import annotations

import re

from quadkit.logging import get_logger

logger = get_logger(__name__)


class HeaderSanitizer:
    """Sanitizer that strips CRLF characters from header values."""

    _CRLF_RE = re.compile(r"[\r\n]")

    def sanitize_header_value(self, value: str) -> str:
        """Replace CRLF characters with a space.

        Args:
            value: The raw header value to sanitize.

        Returns:
            The sanitized header value with CR/LF replaced by spaces.
        """
        if not value:
            return value

        sanitized = self._CRLF_RE.sub(" ", value)
        if sanitized != value:
            logger.warning(
                "security.crlf_injection_detected",
                original_length=len(value),
                sanitized_length=len(sanitized),
            )
        return sanitized


__all__ = ["HeaderSanitizer"]
