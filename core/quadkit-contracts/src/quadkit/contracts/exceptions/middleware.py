"""Middleware exceptions contract."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class MiddlewareGuardError(QuadkitError):
    """Raised when a middleware guard denies access."""

    _code = "QK_ERR_MW_001"

    def __init__(
        self,
        message: str = "Access denied",
        guard: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.guard = guard


__all__ = ["MiddlewareGuardError"]
