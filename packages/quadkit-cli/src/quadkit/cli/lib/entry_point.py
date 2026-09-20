from __future__ import annotations

"""Shared helpers for resolving Python module entry points."""

import ast
from pathlib import Path

from quadkit.logging import get_logger

logger = get_logger(__name__)


def path_to_module(file_path: str) -> str:
    """Convert a file path to a dotted Python module string.

    E.g. ``src/my_app/app.py`` → ``my_app.app``.

    Args:
        file_path: File path like ``src/myapp/main.py`` or a plain filename.

    Returns:
        Dotted module name like ``myapp.main``.
    """
    p = Path(file_path)
    parts = list(p.with_suffix("").parts)

    # Strip leading ``src`` directory if present
    if parts and parts[0] == "src":
        parts = parts[1:]

    return ".".join(parts)


def detect_factory_attr(file_path: str) -> str | None:
    """Return the first callable attr name of interest in the file.

    Checks for ``create_app`` first (factory pattern), then ``app`` /
    ``asgi_app`` (module-level ASGI object pattern, including imported names).

    Args:
        file_path: Path to the Python source file to inspect.

    Returns:
        The attribute name (``'app'``, ``'asgi_app'``, ``'create_app'``, …)
        or ``None`` when no recognised name is found or the file cannot be
        parsed.
    """
    try:
        source = Path(file_path).read_text()
        tree = ast.parse(source)
    except Exception:  # noqa: BLE001 — a bad entry point config is treated as absent
        return None

    # Collect all top-level names: function defs, assignments, and imports
    top_level: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            top_level.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    top_level.add(t.id)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                top_level.add(name)

    for candidate in ("create_app", "app", "asgi_app"):
        if candidate in top_level:
            return candidate

    return None


__all__ = ["detect_factory_attr", "path_to_module"]
