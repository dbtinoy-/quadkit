"""Built-in middleware implementations for common cross-cutting concerns.

Provides reusable middleware organized by domain:
- ``observability`` — timing, logging, correlation ID
- ``resilience`` — retry, timeout, circuit breaker, rate limiting
- ``validation`` — input validation, error handling
- ``caching`` — result caching
- ``di`` — DI scope management
- ``routing`` — conditional application
"""

from __future__ import annotations

from quadkit.middleware.builtins.caching import CachingMiddleware
from quadkit.middleware.builtins.di import ScopedMiddleware
from quadkit.middleware.builtins.observability import (
    CorrelationIdMiddleware,
    LoggingMiddleware,
    TimingMiddleware,
)
from quadkit.middleware.builtins.resilience import (
    CircuitBreakerMiddleware,
    RateLimiterMiddleware,
    RetryMiddleware,
    TimeoutMiddleware,
)
from quadkit.middleware.builtins.routing import ConditionalMiddleware
from quadkit.middleware.builtins.validation import (
    ErrorHandlerMiddleware,
    ValidationMiddleware,
)

__all__ = [
    "CachingMiddleware",
    "CircuitBreakerMiddleware",
    "ConditionalMiddleware",
    "CorrelationIdMiddleware",
    "ErrorHandlerMiddleware",
    "LoggingMiddleware",
    "RateLimiterMiddleware",
    "RetryMiddleware",
    "ScopedMiddleware",
    "TimeoutMiddleware",
    "TimingMiddleware",
    "ValidationMiddleware",
]
