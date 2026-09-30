"""Logging protocols for Quadkit Framework.

This module defines the standard logging interface used across the
framework to avoid circular dependencies and allow sub-packages to
remain independent of the concrete logging implementation.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LoggerProtocol(Protocol):
    """Protocol for structured logging with context support.

    The message is positional-only.  Every keyword reaching a log call is a
    structured *field*, so binding one of them to the message parameter
    would reserve an ordinary word (``msg``) that callers are entitled to
    log — and ``logger.info("mail_sent", msg=body)`` would fail with
    "got multiple values for argument 'msg'".
    """

    def debug(self, msg: str, /, *args: Any, **kwargs: Any) -> None: ...
    def info(self, msg: str, /, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, msg: str, /, *args: Any, **kwargs: Any) -> None: ...
    def error(self, msg: str, /, *args: Any, **kwargs: Any) -> None: ...
    def critical(self, msg: str, /, *args: Any, **kwargs: Any) -> None: ...
    def exception(self, msg: str, /, *args: Any, **kwargs: Any) -> None: ...

    def bind(self, **kwargs: Any) -> LoggerProtocol:
        """Add context variables to the logger."""
        ...

    def unbind(self, *keys: str) -> LoggerProtocol:
        """Remove context variables from the logger."""
        ...


@runtime_checkable
class LoggerFactoryProtocol(Protocol):
    """Protocol for creating/retrieving named logger instances."""

    def get_logger(self, name: str | None = None) -> LoggerProtocol:
        """Get a logger instance for the given name."""
        ...


@runtime_checkable
class RedactorProtocol(Protocol):
    """Protocol for sensitive data redaction."""

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of ``data`` with sensitive values masked."""
        ...

    def redact_value(self, value: Any) -> Any:
        """Redact a single value if it matches a sensitive pattern."""
        ...


__all__ = ["LoggerFactoryProtocol", "LoggerProtocol", "RedactorProtocol"]
