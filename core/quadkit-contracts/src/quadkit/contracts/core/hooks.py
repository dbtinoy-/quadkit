"""Hook registry protocol and priority enum for framework extensibility."""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable


class HookPriority(IntEnum):
    """Named priority levels for hook handlers.

    Lower values run first. Custom integer values are accepted anywhere
    a priority is expected — these named levels are conveniences.

    Spacing between levels leaves room for application-specific
    intermediate values (e.g. ``HookPriority.EARLY + 10``).
    """

    EARLIEST = 0
    EARLY = 50
    NORMAL = 100
    LATE = 200
    LATEST = 300


@runtime_checkable
class HookRegistryProtocol(Protocol):
    """Structural protocol for hook registries.

    Defines the contract for action hooks (fire-and-forget, error-isolated)
    and filter hooks (value-pipeline, error-propagating) with priority ordering.
    """

    def register_action(
        self,
        hook_name: str,
        handler: Callable[..., Any],
        priority: int = 100,
        *,
        once: bool = False,
    ) -> None:
        """Register an action handler for the given hook.

        Args:
            hook_name: The hook point name.
            handler: Callable to invoke. Can be sync or async.
            priority: Lower values run first. Defaults to 100.
            once: If True, auto-remove handler after first invocation.
        """
        ...

    def register_filter(
        self,
        hook_name: str,
        handler: Callable[..., Any],
        priority: int = 100,
        *,
        once: bool = False,
    ) -> None:
        """Register a filter handler for the given hook.

        Args:
            hook_name: The hook point name.
            handler: Callable that receives and returns a value.
            priority: Lower values run first. Defaults to 100.
            once: If True, auto-remove handler after first invocation.
        """
        ...

    def unregister_action(self, hook_name: str, handler: Callable[..., Any]) -> bool:
        """Remove an action handler. Returns True if found and removed."""
        ...

    def unregister_filter(self, hook_name: str, handler: Callable[..., Any]) -> bool:
        """Remove a filter handler. Returns True if found and removed."""
        ...

    async def call_action(self, hook_name: str, **kwargs: Any) -> None:
        """Invoke all action handlers. Errors are isolated and logged."""
        ...

    async def apply_filter(self, hook_name: str, value: Any, **kwargs: Any) -> Any:
        """Pass value through all filter handlers. Errors propagate."""
        ...

    def has_action(self, hook_name: str) -> bool:
        """Check if any action handlers are registered."""
        ...

    def has_filter(self, hook_name: str) -> bool:
        """Check if any filter handlers are registered."""
        ...

    def clear(self, hook_name: str | None = None) -> None:
        """Clear handlers for a specific hook, or all hooks."""
        ...


__all__ = [
    "HookPriority",
    "HookRegistryProtocol",
]
