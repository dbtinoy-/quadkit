"""Ambient DI resolver context for the current async task.

Provides the :data:`current_resolver_var` ContextVar and the
:func:`get_resolver` helper, which allow framework internals to
discover the active resolver without requiring explicit propagation.
"""

from __future__ import annotations

import contextvars
from typing import Any

from quadkit.contracts.core.di import ContainerResolverProtocol


def get_resolver(context: Any) -> ContainerResolverProtocol | None:
    """Extract a resolver from a framework context object.

    Avoids the service-locator anti-pattern by searching well-known
    attributes of the provided context (e.g. Request, PipelineContext)
    rather than calling the container directly.

    Args:
        context: The object to extract the resolver from.

    Returns:
        The resolver if found, otherwise ``None``.
    """
    if context is None:
        return None

    if isinstance(context, ContainerResolverProtocol):
        return context

    for attr in ("resolver", "container", "_container"):
        val = getattr(context, attr, None)
        if isinstance(val, ContainerResolverProtocol):
            return val

    state = getattr(context, "state", None)
    if state is not None:
        val = getattr(state, "resolver", None) or getattr(state, "container", None)
        if isinstance(val, ContainerResolverProtocol):
            return val

    app = getattr(context, "app", None)
    if app is not None:
        val = getattr(app, "container", None) or getattr(app, "resolver", None)
        if isinstance(val, ContainerResolverProtocol):
            return val

    return None


current_resolver_var: contextvars.ContextVar[ContainerResolverProtocol | None] = (
    contextvars.ContextVar("current_resolver", default=None)
)

__all__ = ["current_resolver_var", "get_resolver"]
