"""Helpers for safe diagnostic logging and error reporting."""

from __future__ import annotations


def safe_error_type(error: object) -> str:
    """Return only an error's class name without reading its message.

    Exception messages can contain credentials, private paths, upstream
    response bodies, or user input. This helper deliberately does not call
    ``str(error)`` or inspect traceback information.
    """
    return type(error).__name__


__all__ = ["safe_error_type"]
