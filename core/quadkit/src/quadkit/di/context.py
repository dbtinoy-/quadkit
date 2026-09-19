from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Annotated, NamedTuple, get_args, get_origin

if TYPE_CHECKING:
    from quadkit.di.module.graph import CompiledModuleGraph

__all__ = [
    "ModuleContextTokens",
    "check_visibility",
    "clear_module_context",
    "get_current_module",
    "set_module_context",
]

_current_module: ContextVar[type | None] = ContextVar(
    "quadkit_current_module", default=None
)
_module_graph: ContextVar[CompiledModuleGraph | None] = ContextVar(
    "quadkit_module_graph", default=None
)


class ModuleContextTokens(NamedTuple):
    """Tokens returned by set_module_context for safe restoration.

    Pass to clear_module_context() in a finally block to restore prior
    ContextVar state exactly, regardless of what value was set before.
    """

    module_token: Token[type | None]
    graph_token: Token  # Token[CompiledModuleGraph | None] — unparameterized at runtime


def get_current_module() -> type | None:
    """Return the module class currently executing a boot() call, or None.

    Returns:
        The module class owning the current provider being booted, or None
        if no module context is active (standalone resolution).
    """
    return _current_module.get()


def set_module_context(
    module_class: type | None,
    graph: CompiledModuleGraph | None,
) -> ModuleContextTokens:
    """Set the active module context and return tokens for restoration.

    Call before provider.boot(), then pass tokens to clear_module_context()
    in a finally block.

    Args:
        module_class: Module class owning the current provider, or None.
        graph: Compiled module graph for visibility lookups, or None.

    Returns:
        Tokens to pass to clear_module_context() for restoration.
    """
    return ModuleContextTokens(
        module_token=_current_module.set(module_class),
        graph_token=_module_graph.set(graph),
    )


def clear_module_context(tokens: ModuleContextTokens) -> None:
    """Restore ContextVar state using tokens from set_module_context.

    Always call in a finally block to guarantee cleanup even on exceptions.

    Args:
        tokens: Tokens returned by set_module_context.
    """
    _current_module.reset(tokens.module_token)
    _module_graph.reset(tokens.graph_token)


def check_visibility(service_type: type) -> bool:
    """Return True if service_type is visible to the current module context.

    Returns True unconditionally when no module context is set (standalone
    resolution has no visibility restrictions). Also returns True when a
    module is set but the graph is None (half-initialized state).

    Args:
        service_type: The type being resolved.

    Returns:
        True if visible or no context, False if module context exists and type
        is not in its visibility set.
    """
    module = _current_module.get()
    graph = _module_graph.get()
    if module is None or graph is None:
        return True
    if get_origin(service_type) is Annotated:
        annotated_args = get_args(service_type)
        if annotated_args:
            service_type = annotated_args[0]
    return graph.is_visible(module, service_type)
