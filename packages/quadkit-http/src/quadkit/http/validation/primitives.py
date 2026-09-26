"""Numeric and primitive input validation utilities for quadkit.http.

Validates ports, timeouts, and positive integers. Raises
:class:`~quadkit.http.exceptions.HTTPError` on invalid input so callers get a
well-typed infrastructure error.
"""

from __future__ import annotations

from quadkit.http.exceptions import HTTPClientError


def validate_port(port: int) -> None:
    """Validate a TCP port number.

    Args:
        port: Port number (must be 1–65535).

    Raises:
        HTTPError: If the port is not an integer or is out of range.
    """
    if not isinstance(port, int):
        raise HTTPClientError("Port must be an integer")
    if port < 1 or port > 65535:
        raise HTTPClientError(f"Port must be between 1 and 65535, got {port}")


def validate_timeout(timeout: float | None) -> None:
    """Validate a timeout value.

    Args:
        timeout: Timeout in seconds, or ``None`` for no timeout.

    Raises:
        HTTPError: If ``timeout`` is not a positive number.
    """
    if timeout is None:
        return
    if not isinstance(timeout, (int, float)):
        raise HTTPClientError("Timeout must be a number")
    if timeout <= 0:
        raise HTTPClientError(f"Timeout must be positive, got {timeout}")


def validate_positive_int(value: int, field: str = "value") -> None:
    """Validate that *value* is a positive integer.

    Args:
        value: Integer to validate.
        field: Field name used in the error message.

    Raises:
        HTTPError: If ``value`` is not a positive integer.
    """
    if not isinstance(value, int):
        raise HTTPClientError(f"{field} must be an integer")
    if value <= 0:
        raise HTTPClientError(f"{field} must be positive, got {value}")


__all__ = [
    "validate_port",
    "validate_positive_int",
    "validate_timeout",
]
