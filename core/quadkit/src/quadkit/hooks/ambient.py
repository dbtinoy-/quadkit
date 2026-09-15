"""Ambient hook registry — process-wide default :class:`HookRegistry`.

The hook registry is ambient by design: extensions fire and register
hooks without DI plumbing, mirroring the ambient clock/identity
primitives.  A default registry backs the API; tests override via
``use()`` / ``install()``.

Example:
    ```python
    from quadkit.hooks.ambient import fire, register_action

    async def handler(**kwargs: Any) -> None:
        await notify(**kwargs)

    register_action("order.created", handler)
    await fire("order.created", order_id="42")
    ```
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import contextvars
from typing import Any

from quadkit.contracts.core.hooks import HookPriority
from quadkit.hooks.registry import HookRegistry

_registry: contextvars.ContextVar[HookRegistry] = contextvars.ContextVar[HookRegistry](
    "quadkit_hooks",
    default=HookRegistry("default"),  # noqa: B039
)


def install(registry: HookRegistry) -> None:
    """Install a process-wide hook registry. Idempotent; last call wins."""
    _registry.set(registry)


def current() -> HookRegistry:
    """Return the active hook registry (rarely needed by callers)."""
    return _registry.get()


def register_action(
    hook_name: str,
    handler: Any,
    priority: int = HookPriority.NORMAL,
    *,
    once: bool = False,
) -> None:
    """Register an action handler on the ambient hook registry."""
    _registry.get().register_action(
        hook_name,
        handler,
        priority=priority,
        once=once,
    )


async def fire(hook_name: str, **kwargs: Any) -> None:
    """Invoke all action handlers for the named hook, error-isolated."""
    await _registry.get().call_action(hook_name, **kwargs)


@contextmanager
def use(registry: HookRegistry) -> Iterator[None]:
    """Override the ambient hook registry for the duration of a block."""
    token = _registry.set(registry)
    try:
        yield
    finally:
        _registry.reset(token)


__all__ = ["current", "fire", "install", "register_action", "use"]
