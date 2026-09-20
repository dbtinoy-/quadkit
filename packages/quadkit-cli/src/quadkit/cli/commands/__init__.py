"""Quadkit CLI command modules.

Command modules resolve lazily (PEP 562; plans/09172026 C-01): importing a
single command module — e.g. ``quadkit.cli.commands.meta`` for
``quadkit version`` — must not import the other fourteen. The names remain
importable exactly as before: ``from quadkit.cli.commands import new``.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "add",
    "config",
    "contrib",
    "db",
    "dev",
    "events",
    "gen",
    "init",
    "inspect",
    "new",
    "project",
    "run",
    "shell",
    "system",
]

_LAZY_MODULES: dict[str, str] = {
    name: f"quadkit.cli.commands.{name}" for name in __all__
}


def __getattr__(name: str) -> Any:
    """Import a command module on first access."""
    module_path = _LAZY_MODULES.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = import_module(module_path)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_MODULES))
