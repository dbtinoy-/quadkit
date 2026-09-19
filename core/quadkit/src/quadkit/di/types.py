"""Type definitions for the DI subsystem.

Re-exports scope and provider lifecycle enums from their contract sources.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias, TypeVar

from quadkit.contracts.core.provider import ProviderPriority as ProviderPriority
from quadkit.contracts.core.scopes import ServiceScope as ServiceScope
from quadkit.di.provider import ProviderState as ProviderState

T = TypeVar("T")  # Generic resolution type

ServiceFactory: TypeAlias = type[T] | Callable[..., T] | Callable[..., Awaitable[T]]

__all__ = [
    "ProviderPriority",
    "ProviderState",
    "ServiceFactory",
    "ServiceScope",
    "T",
]
