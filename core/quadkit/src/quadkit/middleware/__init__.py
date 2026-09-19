"""Middleware system for Quadkit Framework.

Provides middleware pipeline, registry, common middleware implementations,
and exception filter chain for composable request processing.

Exports:
    Middleware, MiddlewareProtocol, GuardProtocol: Contracts.
    MiddlewareGuardError: Raised when a guard rejects a request.
    MiddlewareChain, MiddlewarePipeline, MiddlewareRegistry: Pipeline components.
    ExceptionFilterChain: Ordered exception handler chain.
    CachingMiddleware, CorrelationIdMiddleware, ...: Built-in middleware.
"""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.middleware.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.app.pipeline import MiddlewarePipeline
    from quadkit.contracts.exceptions.middleware import MiddlewareGuardError
    from quadkit.contracts.web import (
        GuardProtocol,
        Middleware,
        MiddlewareProtocol,
    )
    from quadkit.middleware.builtins import (
        CachingMiddleware,
        CircuitBreakerMiddleware,
        ConditionalMiddleware,
        CorrelationIdMiddleware,
        ErrorHandlerMiddleware,
        LoggingMiddleware,
        RateLimiterMiddleware,
        RetryMiddleware,
        ScopedMiddleware,
        TimeoutMiddleware,
        TimingMiddleware,
        ValidationMiddleware,
    )
    from quadkit.middleware.core.chain import MiddlewareChain
    from quadkit.middleware.core.exception_filters import ExceptionFilterChain
    from quadkit.middleware.core.registry import MiddlewareRegistry

_LAZY_IMPORTS: dict[str, str] = {
    # contracts
    "GuardProtocol": "quadkit.contracts.web",
    "MiddlewareGuardError": "quadkit.contracts.exceptions.middleware",
    "Middleware": "quadkit.contracts.core",
    "MiddlewareProtocol": "quadkit.contracts.core",
    # implementations
    "CachingMiddleware": "quadkit.middleware.builtins",
    "CircuitBreakerMiddleware": "quadkit.middleware.builtins",
    "ConditionalMiddleware": "quadkit.middleware.builtins",
    "CorrelationIdMiddleware": "quadkit.middleware.builtins",
    "ErrorHandlerMiddleware": "quadkit.middleware.builtins",
    "LoggingMiddleware": "quadkit.middleware.builtins",
    "RateLimiterMiddleware": "quadkit.middleware.builtins",
    "RetryMiddleware": "quadkit.middleware.builtins",
    "ScopedMiddleware": "quadkit.middleware.builtins",
    "TimingMiddleware": "quadkit.middleware.builtins",
    "TimeoutMiddleware": "quadkit.middleware.builtins",
    "ValidationMiddleware": "quadkit.middleware.builtins",
    "ExceptionFilterChain": "quadkit.middleware.core.exception_filters",
    "InfrastructureExceptionFilter": "quadkit.middleware.core.exception_filters",
    "MiddlewarePolicyExceptionFilter": "quadkit.middleware.core.exception_filters",
    "NotFoundExceptionFilter": "quadkit.middleware.core.exception_filters",
    "ValidationExceptionFilter": "quadkit.middleware.core.exception_filters",
    "MiddlewareChain": "quadkit.middleware.core.chain",
    "MiddlewarePipeline": "quadkit.app.pipeline",
    "MiddlewareRegistry": "quadkit.middleware.core.registry",
    # types
    "C": "quadkit.middleware.types",
    "MiddlewareCallable": "quadkit.middleware.types",
    "NextHandler": "quadkit.middleware.types",
    # constants
    "DEFAULT_CIRCUIT_FAILURE_THRESHOLD": "quadkit.middleware.constants",
    "DEFAULT_CIRCUIT_RECOVERY_TIMEOUT": "quadkit.middleware.constants",
    "DEFAULT_RATE_LIMIT_MAX_REQUESTS": "quadkit.middleware.constants",
    "DEFAULT_RATE_LIMIT_WINDOW": "quadkit.middleware.constants",
    "DEFAULT_RETRY_COUNT": "quadkit.middleware.constants",
    "DEFAULT_RETRY_DELAY": "quadkit.middleware.constants",
    "DEFAULT_TIMEOUT": "quadkit.middleware.constants",
    "HOOK_CIRCUIT_BREAKER_CLOSED": "quadkit.middleware.constants",
    "HOOK_CIRCUIT_BREAKER_OPENED": "quadkit.middleware.constants",
    "HOOK_RATE_LIMIT_EXCEEDED": "quadkit.middleware.constants",
    "HOOK_TIMEOUT": "quadkit.middleware.constants",
    # --- added by migration script ---
    "MiddlewareConfig": "quadkit.middleware.config",
    "MiddlewareError": "quadkit.middleware.exceptions",
    "MiddlewareExecutionError": "quadkit.middleware.exceptions",
    "MiddlewareConfigurationError": "quadkit.middleware.exceptions",
    "MiddlewareChainError": "quadkit.middleware.exceptions",
    "MiddlewareTimeoutError": "quadkit.middleware.exceptions",
    "MiddlewareAuthError": "quadkit.middleware.exceptions",
    "MiddlewarePolicyError": "quadkit.middleware.exceptions",
    "MiddlewareRateLimitError": "quadkit.middleware.exceptions",
    "MiddlewareCircuitOpenError": "quadkit.middleware.exceptions",
    "MiddlewareModule": "quadkit.middleware.module",
    "MiddlewareProvider": "quadkit.middleware.di.provider",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = list(_LAZY_IMPORTS.keys())
