"""HTTP-specific sanitization package for quadkit-web.

Contains header sanitization (CRLF injection prevention).
Transport-agnostic sanitization (HTML, URL, filename) lives in
``quadkit.security.sanitization`` (core).
"""

from __future__ import annotations

from quadkit.web.security.sanitization.header import HeaderSanitizer

__all__ = ["HeaderSanitizer"]
