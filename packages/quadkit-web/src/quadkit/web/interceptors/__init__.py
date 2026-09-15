"""Interceptor system for Quadkit Web.

Two interception models are available:

- **HTTP Pipeline** (``interceptors.pipeline``): For HTTP request/response interception.
- **AOP Proxy** (``interceptors.aop``): For general-purpose method interception.
"""

from __future__ import annotations

from quadkit.di.extensions.aop_interceptors import (
    InterceptorTimeoutError,
    MethodInterceptorProtocol,
    MethodInterceptorRegistry,
    MethodInterceptorRegistryManager,
)
from quadkit.web.interceptors.builtin.cache import CacheInterceptor

# Built-in interceptors
from quadkit.web.interceptors.builtin.logging import LoggingInterceptor
from quadkit.web.interceptors.builtin.timing import HandlerTimingInterceptor
from quadkit.web.interceptors.builtin.transform import TransformInterceptor
from quadkit.web.interceptors.pipeline import InterceptorPipeline
from quadkit.web.protocols import (
    CallHandlerProtocol,
    ExecutionContextProtocol,
    WebInterceptorBase,
    WebInterceptorProtocol,
)
from quadkit.web.routing.execution_context import (
    WebExecutionContext,
)

__all__ = [
    "CacheInterceptor",
    # Protocols
    "CallHandlerProtocol",
    "ExecutionContextProtocol",
    "HandlerTimingInterceptor",
    # Pipeline
    "InterceptorPipeline",
    # Timeout
    "InterceptorTimeoutError",
    # Built-in interceptors
    "LoggingInterceptor",
    # AOP
    "MethodInterceptorProtocol",
    "MethodInterceptorRegistry",
    "MethodInterceptorRegistryManager",
    "TransformInterceptor",
    # Context
    "WebExecutionContext",
    "WebInterceptorBase",
    "WebInterceptorProtocol",
]
