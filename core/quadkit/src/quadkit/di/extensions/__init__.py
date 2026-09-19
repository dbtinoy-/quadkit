"""DI extension points — discovery, interceptors, strategies, and protocol validation."""

from __future__ import annotations

from quadkit.di.extensions.discovery import ProviderScanner
from quadkit.di.extensions.interceptors import (
    DIInterceptor,
    InterceptorRegistry,
    wrap_with_interceptors,
)
from quadkit.di.extensions.strategies import ResolutionStrategy
from quadkit.di.extensions.validator import ProtocolValidator, validate_protocol

__all__ = [
    "DIInterceptor",
    "InterceptorRegistry",
    "ProtocolValidator",
    "ProviderScanner",
    "ResolutionStrategy",
    "validate_protocol",
    "wrap_with_interceptors",
]
