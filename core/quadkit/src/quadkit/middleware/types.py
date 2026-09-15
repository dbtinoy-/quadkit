"""Type definitions for the middleware subsystem.

Callable type aliases and TypeVars used in the middleware pipeline.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias, TypeVar

NextHandler: TypeAlias = Callable[[Any], Awaitable[Any]]
"""Callable for the next handler in a middleware chain."""

MiddlewareCallable: TypeAlias = Callable[[Any, NextHandler], Awaitable[Any]]
"""Callable signature for a middleware handler."""

C = TypeVar("C")  # Context type
"""TypeVar for the request/response context type."""

__all__ = [
    "C",
    "MiddlewareCallable",
    "NextHandler",
]
