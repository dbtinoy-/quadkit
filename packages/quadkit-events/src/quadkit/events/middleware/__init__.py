"""AbstractMiddleware module for CQRS buses.

This module provides reusable middleware components:
- LoggingMiddleware: Log command/query execution
- ValidationMiddleware: Validate messages before handling
- TransactionMiddleware: Wrap handlers in transactions
- RetryMiddleware: Retry failed handlers
- MetricsMiddleware: Collect execution metrics
- CircuitBreakerMiddleware: Prevent cascading failures
"""

from __future__ import annotations

from quadkit.events.middleware.base import (
    AbstractMiddleware,
    MiddlewareChain,
    NextHandler,
    middleware,
)
from quadkit.events.middleware.circuit_breaker import CircuitBreakerMiddleware
from quadkit.events.middleware.logging import LoggingMiddleware
from quadkit.events.middleware.metrics import (
    MessageMetrics,
    MetricsMiddleware,
)
from quadkit.events.middleware.retry import RetryMiddleware
from quadkit.events.middleware.transaction import (
    TransactionContext,
    TransactionMiddleware,
    UnitOfWorkMiddleware,
)
from quadkit.events.middleware.validation import ValidationMiddleware

__all__ = [
    "AbstractMiddleware",
    "CircuitBreakerMiddleware",
    "LoggingMiddleware",
    "MessageMetrics",
    "MetricsMiddleware",
    "MiddlewareChain",
    "NextHandler",
    "RetryMiddleware",
    "TransactionContext",
    "TransactionMiddleware",
    "UnitOfWorkMiddleware",
    "ValidationMiddleware",
    "middleware",
]
