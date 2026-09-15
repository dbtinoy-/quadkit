"""Exceptions for the app subsystem.

Provides the ``AppError`` base class and lifecycle-specific subtypes.
"""

from __future__ import annotations

from quadkit.contracts.exceptions import QuadkitError


class AppError(QuadkitError):
    """Base exception for all app errors."""

    _code: str = "QK_ERR_APP_001"


class AppStartupError(AppError):
    """Raised when the application fails to start or a provider fails during boot."""

    _code: str = "QK_ERR_APP_002"


class AppShutdownError(AppError):
    """Raised when the application cannot complete a graceful shutdown."""

    _code: str = "QK_ERR_APP_003"


__all__ = [
    "AppError",
    "AppShutdownError",
    "AppStartupError",
]
