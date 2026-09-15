"""Internal types for the hooks subpackage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from quadkit.contracts.core.hooks import HookPriority

ActionHandler = Callable[..., Any]
"""Type alias for action hook handlers. Accepts **kwargs, returns None."""

FilterHandler = Callable[..., Any]
"""Type alias for filter hook handlers. Accepts (value, **kwargs), returns value."""


@dataclass(frozen=True, slots=True)
class HookEntry:
    """Internal entry representing a registered hook handler.

    Frozen for safe storage in sorted lists. Uses identity comparison
    (``id()``) for removal via ``unregister_*()``.

    Args:
        priority: Sort key. Lower values execute first.
        handler: The callable to invoke.
        once: If True, auto-remove after first invocation.
    """

    priority: int
    handler: Callable[..., Any]
    once: bool = False


__all__ = [
    "ActionHandler",
    "FilterHandler",
    "HookEntry",
    "HookPriority",
]
