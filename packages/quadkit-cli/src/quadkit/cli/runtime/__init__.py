"""CLI runtime components — context management and error handling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.cli.runtime.context import CLIContext
    from quadkit.cli.runtime.error_handler import handle_errors

__all__ = ["CLIContext", "handle_errors"]

_LAZY_IMPORTS: dict[str, str] = {
    "CLIContext": "quadkit.cli.runtime.context",
    "handle_errors": "quadkit.cli.runtime.error_handler",
}


def __getattr__(name: str) -> Any:
    """Resolve runtime re-exports lazily (PEP 562).

    Keeps ``from quadkit.cli.runtime import CLIContext`` working while
    ensuring that importing :mod:`quadkit.cli.runtime.main` does not pay
    for the context chain (plans/09172026 C-03).
    """
    module_path = _LAZY_IMPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_IMPORTS))
