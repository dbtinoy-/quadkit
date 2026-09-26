"""Model lifecycle hooks for the declarative schema model system.

Registry and decorators for ``before_*`` / ``after_*`` model events,
fired via :func:`fire_hooks`.
"""

from __future__ import annotations

from typing import Any

# Registry for model lifecycle hooks
_model_hooks: dict[str, dict[str, list]] = {}


def _register_hook(
    model_name: str,
    event: str,
    handler: Any,
) -> None:
    """Register a lifecycle hook for a model."""
    _model_hooks.setdefault(model_name, {}).setdefault(event, []).append(
        handler,
    )


def before_create(func: Any) -> Any:
    """Decorator: called before entity creation."""
    func._hook_event = "before_create"
    return func


def after_create(func: Any) -> Any:
    """Decorator: called after entity creation."""
    func._hook_event = "after_create"
    return func


def before_update(func: Any) -> Any:
    """Decorator: called before entity update."""
    func._hook_event = "before_update"
    return func


def after_update(func: Any) -> Any:
    """Decorator: called after entity update."""
    func._hook_event = "after_update"
    return func


def before_delete(func: Any) -> Any:
    """Decorator: called before entity deletion."""
    func._hook_event = "before_delete"
    return func


def after_delete(func: Any) -> Any:
    """Decorator: called after entity deletion."""
    func._hook_event = "after_delete"
    return func


async def fire_hooks(
    model_name: str,
    event: str,
    entity: Any,
) -> None:
    """Fire all registered hooks for a model event."""
    hooks = _model_hooks.get(model_name, {}).get(event, [])
    for hook in hooks:
        import asyncio

        if asyncio.iscoroutinefunction(hook):
            await hook(entity)
        else:
            hook(entity)
