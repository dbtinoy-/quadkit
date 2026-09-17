"""Filters Domain - Exception Handling"""

from __future__ import annotations

from quadkit.contracts.web.protocols import ExceptionFilterProtocol
from quadkit.web.filters.adapters import CallbackExceptionFilter
from quadkit.web.filters.builtin import (
    DefaultExceptionFilter,
    DependencyResolutionFilter,
    ValidationErrorFilter,
)
from quadkit.web.filters.decorators import use_filters

__all__ = [
    "CallbackExceptionFilter",
    "DefaultExceptionFilter",
    "DependencyResolutionFilter",
    "ExceptionFilterProtocol",
    "ValidationErrorFilter",
    "use_filters",
]
