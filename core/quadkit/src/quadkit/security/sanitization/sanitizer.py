"""Input sanitizer implementation."""

from __future__ import annotations

import re
from typing import Any

from quadkit.contracts.security import InputSanitizerProtocol
from quadkit.logging import get_logger
from quadkit.security.config import InputSanitizerConfig
from quadkit.security.sanitization.filename import FilenameSanitizer
from quadkit.security.sanitization.html import HtmlSanitizer
from quadkit.security.sanitization.url import UrlSanitizer

logger = get_logger(__name__)

# Inline CRLF stripping — header.py is HTTP-specific and lives in quadkit-web.
_CRLF_RE = re.compile(r"[\r\n]")


class InputSanitizer(InputSanitizerProtocol):
    """Sanitize user input to defend against injection attacks.

    Composes specialized sanitizers for different input types:
    filenames, HTML, and URLs. Provides a unified interface for
    comprehensive input sanitization.
    """

    def __init__(self, config: InputSanitizerConfig | None = None) -> None:
        """Initialize the sanitizer with optional custom config.

        Args:
            config: Optional sanitizer configuration. If None, uses defaults.
        """
        self._config = config or InputSanitizerConfig()
        self._filename = FilenameSanitizer()
        self._html = HtmlSanitizer(self._config)
        self._url = UrlSanitizer()

    @property
    def config(self) -> InputSanitizerConfig:
        """Return the sanitizer configuration."""
        return self._config

    def sanitize_filename(self, filename: str) -> str:
        """Keep only safe characters in filenames.

        Args:
            filename: Filename to sanitize.

        Returns:
            Sanitized filename with unsafe characters replaced.
        """
        return self._filename.sanitize_filename(filename)

    def sanitize_sql_like(self, value: str, escape_char: str = "\\") -> str:
        """Escape SQL LIKE wildcards in the provided value.

        Args:
            value: Value to escape.
            escape_char: Character to use for escaping (default: backslash).

        Returns:
            Escaped value safe for SQL LIKE clauses.
        """
        return self._filename.sanitize_sql_like(value, escape_char)

    def sanitize_header_value(self, value: str) -> str:
        """Replace CRLF characters with a space to prevent header injection.

        Args:
            value: Header value to sanitize.

        Returns:
            Header value with CRLF characters replaced.
        """
        if not value:
            return value
        sanitized = _CRLF_RE.sub(" ", value)
        if sanitized != value:
            logger.warning(
                "security.crlf_injection_detected",
                original_length=len(value),
                sanitized_length=len(sanitized),
            )
        return sanitized

    def strip_html(self, value: str) -> str:
        """Strip disallowed HTML tags from the value.

        Args:
            value: Value to strip.

        Returns:
            Value with HTML tags removed according to configuration.
        """
        return self._html.strip_html(value)

    def escape_html(self, value: str) -> str:
        """Escape HTML special characters.

        Args:
            value: Value to escape.

        Returns:
            Value with HTML special characters escaped.
        """
        return self._html.escape_html(value)

    def sanitize_url(self, url: str) -> str:
        """Return an empty string when the URL uses a dangerous scheme.

        Args:
            url: URL to sanitize.

        Returns:
            Empty string if dangerous scheme detected, otherwise the URL.
        """
        return self._url.sanitize_url(url)

    def sanitize_path(self, path: str) -> str:
        """Strip traversal sequences and null bytes from file paths.

        Args:
            path: File path to sanitize.

        Returns:
            Path with traversal sequences removed.
        """
        return self._url.sanitize_path(path)

    def is_safe_url_for_request(self, url: str) -> bool:
        """Return False if the URL resolves to a private or reserved IP.

        Args:
            url: URL to check.

        Returns:
            False if URL targets private/reserved IP, True if safe.
        """
        return self._url.is_safe_url_for_request(url)

    def sanitize(self, value: str) -> str:
        """Sanitize ``value`` based on the configured default mode.

        Supports three modes:
        - ``'strip'``: Remove all HTML tags (requires nh3)
        - ``'escape'``: Escape HTML special characters
        - ``'allow'``: Remove only dangerous tags and attributes (default)

        Args:
            value: Value to sanitize.

        Returns:
            Sanitized value according to configured mode.
        """
        if not value:
            return value

        mode = self._config.default_sanitize_mode
        if mode == "strip":
            result = self.strip_html(value)
        elif mode == "escape":
            result = self.escape_html(value)
        elif mode == "allow":
            result = self._html.strip_dangerous(value)
        else:
            result = value

        if result != value:
            logger.warning(
                "security.injection_detected",
                mode=mode,
                original_length=len(value),
                sanitized_length=len(result),
            )

        return result

    def sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize every string value in ``data``.

        Args:
            data: Dictionary with potentially unsafe string values.

        Returns:
            Dictionary with all string values sanitized.
        """
        if not data:
            return data

        sanitized: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = self.sanitize(value)
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self.sanitize(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        return sanitized


__all__ = ["InputSanitizer"]
