"""Resilience pattern exception classes."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class ResilienceError(QuadkitError):
    """Base resilience error."""

    _code = "QK_ERR_RES_001"

    def __init__(self, message: str = "Resilience error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class RetryError(ResilienceError):
    """Retry operation error."""

    _code = "QK_ERR_RES_002"

    def __init__(self, message: str = "Retry error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class CircuitBreakerError(ResilienceError):
    """Circuit breaker error."""

    _code = "QK_ERR_RES_003"

    def __init__(self, message: str = "Circuit breaker error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class BulkheadError(ResilienceError):
    """Bulkhead/rejection error."""

    _code = "QK_ERR_RES_004"

    def __init__(self, message: str = "Bulkhead rejected", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class FallbackError(ResilienceError):
    """Fallback execution error."""

    _code = "QK_ERR_RES_005"

    def __init__(self, message: str = "Fallback error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class RetryExhaustedError(RetryError):
    """All retry attempts have been exhausted."""

    _code = "QK_ERR_RES_006"

    def __init__(
        self,
        message: str = "All retry attempts exhausted",
        attempts: int = 0,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        details["attempts"] = attempts
        kwargs["details"] = details
        super().__init__(message, **kwargs)
        self.attempts = attempts


class CircuitOpenError(CircuitBreakerError):
    """Circuit breaker is open and rejecting requests."""

    _code = "QK_ERR_RES_007"

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


__all__ = [
    "BulkheadError",
    "CircuitBreakerError",
    "CircuitOpenError",
    "FallbackError",
    "ResilienceError",
    "RetryError",
    "RetryExhaustedError",
]
