"""Resilience pattern enums for Quadkit Framework."""

from __future__ import annotations

from enum import StrEnum


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RetryStrategy(StrEnum):
    """Retry backoff strategy semantics."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


__all__ = ["CircuitState", "RetryStrategy"]
