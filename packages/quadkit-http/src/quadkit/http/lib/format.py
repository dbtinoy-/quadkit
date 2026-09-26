"""Formatting and content-type detection utilities.

Pure functions for formatting timeout values and extracting JSON MIME types
from Content-Type headers — no framework dependencies.
"""

from __future__ import annotations


def format_timeout(timeout: float | None) -> str:
    """Format a timeout value for human-readable display.

    Args:
        timeout: Timeout in seconds, or ``None`` for no timeout.

    Returns:
        Formatted string such as ``"30.0s"`` or ``"no timeout"``.
    """
    if timeout is None:
        return "no timeout"
    return f"{timeout}s"


def extract_json_type(content_type: str) -> str | None:
    """Extract the JSON MIME type from a ``Content-Type`` header value.

    Args:
        content_type: Raw ``Content-Type`` header value.

    Returns:
        The base MIME type if it contains ``"json"``, otherwise ``None``.

    Example:
        >>> extract_json_type("application/json; charset=utf-8")
        'application/json'
        >>> extract_json_type("text/html")
        None
    """
    if not content_type:
        return None
    base_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    return base_type if "json" in base_type else None


__all__ = ["extract_json_type", "format_timeout"]
