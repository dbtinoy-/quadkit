"""Constants for the middleware subsystem.

Typed defaults and magic strings used across the middleware system.
"""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"

# -- Environment Variable Prefix -------------------------------------------

ENV_PREFIX: str = "QK_MIDDLEWARE__"
"""Environment variable prefix for middleware configuration."""

ENV_NESTED_DELIMITER: str = "__"
"""Nested delimiter for environment variables (e.g., QK_MIDDLEWARE__NESTED__KEY)."""

# -- Middleware Defaults ----------------------------------------------------

DEFAULT_CORRELATION_HEADER: str = "X-Correlation-Id"
"""HTTP header name for correlation IDs; consumed by: CorrelationIdMiddleware."""

DEFAULT_RETRY_COUNT: int = 3
"""Default number of retry attempts; consumed by: RetryMiddleware default."""

DEFAULT_RETRY_DELAY: float = 0.1
"""Default delay between retries in seconds; consumed by: RetryMiddleware default."""

# -- Observability hook names -----------------------------------------------

HOOK_MIDDLEWARE_BEFORE: str = "middleware.before"
"""Hook fired before a middleware processes the context."""

HOOK_MIDDLEWARE_AFTER: str = "middleware.after"
"""Hook fired after a middleware processes the context successfully."""

HOOK_MIDDLEWARE_ERROR: str = "middleware.error"
"""Hook fired when a middleware raises an exception."""

HOOK_CIRCUIT_BREAKER_OPENED = "middleware.circuit_breaker.opened"
"""Hook fired when CircuitBreakerMiddleware opens the circuit."""

HOOK_CIRCUIT_BREAKER_CLOSED = "middleware.circuit_breaker.closed"
"""Hook fired when CircuitBreakerMiddleware closes the circuit."""

HOOK_RATE_LIMIT_EXCEEDED = "middleware.rate_limit.exceeded"
"""Hook fired when RateLimiterMiddleware rejects a request."""

HOOK_TIMEOUT = "middleware.timeout"
"""Hook fired when TimeoutMiddleware raises a timeout error."""

# -- New Middleware Defaults ---------------------------------------------------

DEFAULT_TIMEOUT = 30.0
"""Default timeout in seconds for TimeoutMiddleware."""

DEFAULT_CIRCUIT_FAILURE_THRESHOLD = 5
"""Default consecutive failures before CircuitBreakerMiddleware opens."""

DEFAULT_CIRCUIT_RECOVERY_TIMEOUT = 30.0
"""Default seconds before open circuit transitions to half-open."""

DEFAULT_RATE_LIMIT_MAX_REQUESTS = 100
"""Default max requests per window for RateLimiterMiddleware."""

DEFAULT_RATE_LIMIT_WINDOW = 60.0
"""Default rate limit window in seconds."""

__all__ = [
    "DEFAULT_CIRCUIT_FAILURE_THRESHOLD",
    "DEFAULT_CIRCUIT_RECOVERY_TIMEOUT",
    "DEFAULT_CORRELATION_HEADER",
    "DEFAULT_RATE_LIMIT_MAX_REQUESTS",
    "DEFAULT_RATE_LIMIT_WINDOW",
    "DEFAULT_RETRY_COUNT",
    "DEFAULT_RETRY_DELAY",
    "DEFAULT_TIMEOUT",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "HOOK_CIRCUIT_BREAKER_CLOSED",
    "HOOK_CIRCUIT_BREAKER_OPENED",
    "HOOK_MIDDLEWARE_AFTER",
    "HOOK_MIDDLEWARE_BEFORE",
    "HOOK_MIDDLEWARE_ERROR",
    "HOOK_RATE_LIMIT_EXCEEDED",
    "HOOK_TIMEOUT",
]
