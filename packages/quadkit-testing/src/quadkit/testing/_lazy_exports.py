"""Lazy export helpers for the `quadkit.testing` package namespaces.

Package `__init__.py` files export; they do not branch (`AGENTS.md` §4.5).
Several `quadkit.testing` namespaces front modules that ship only with an
optional extra — the web beds need the test client stack, the DB and task beds
need the corresponding provider packages — so the facade declares every public
name in a lazy table and resolves it on first attribute access. A name whose
module is not part of the installation raises `AttributeError`, the same
contract the root facade uses, instead of disappearing from `__all__`.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Final

__all__ = ["module_shipped", "resolve_export"]


def module_shipped(module_path: str) -> bool:
    """Return whether ``module_path`` is importable in this installation.

    The public projection drops modules that depend on packages it does not
    publish, so availability is decided by locating the module — never by
    importing it, which would pull in the optional dependency the facade exists
    to avoid.

    Args:
        module_path: Dotted module path, e.g. ``quadkit.testing.fixtures.db``.

    Returns:
        Whether the module can be located.
    """
    try:
        return importlib.util.find_spec(module_path) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def resolve_export(
    name: str,
    table: dict[str, tuple[str, str]],
    *,
    package: str,
    optional: frozenset[str] = frozenset(),
) -> Any:
    """Import and return one lazily exported name.

    Args:
        name: Attribute requested from the namespace package.
        table: Mapping of public name to ``(module_path, attribute_name)``.
        package: Dotted name of the namespace package, for error messages.
        optional: Module paths that may be absent from this installation.

    Returns:
        The imported attribute.

    Raises:
        AttributeError: When the name is not declared, or its module is not
            part of this installation.
    """
    entry: Final[tuple[str, str] | None] = table.get(name)
    if entry is None:
        raise AttributeError(f"module {package!r} has no attribute {name!r}")
    module_path, attribute = entry
    if module_path in optional and not module_shipped(module_path):
        raise AttributeError(
            f"module {package!r} has no attribute {name!r}: "
            f"{module_path} is not part of this installation"
        )
    module = importlib.import_module(module_path)
    return getattr(module, attribute)
