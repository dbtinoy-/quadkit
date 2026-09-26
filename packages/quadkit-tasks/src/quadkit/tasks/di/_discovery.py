"""Decorated task discovery helpers for ``TaskProvider``."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from quadkit.tasks.decorators import iter_registered_tasks


def import_task_modules(module_paths: tuple[str, ...]) -> None:
    """Import explicitly configured task modules.

    A path that cannot be imported propagates its ``ModuleNotFoundError``: an
    unresolvable root is a configuration error, and silently skipping it would
    present itself as "my scheduled task never runs".
    """
    for module_path in module_paths:
        importlib.import_module(module_path)


def import_task_packages(package_paths: tuple[str, ...]) -> None:
    """Import every module beneath explicitly configured task packages."""
    for package_path in package_paths:
        package = importlib.import_module(package_path)
        package_search_path = getattr(package, "__path__", None)
        if package_search_path is None:
            continue
        prefix = f"{package.__name__}."
        for module_info in pkgutil.walk_packages(package_search_path, prefix=prefix):
            importlib.import_module(module_info.name)


def discover_registered_tasks(
    *,
    task_modules: tuple[str, ...],
    task_packages: tuple[str, ...],
) -> list[Any]:
    """Import configured roots and return decorated task wrappers.

    Args:
        task_modules: Exact module paths to import before discovery. When
            omitted, already-imported decorated tasks are discovered globally.
        task_packages: Package roots to import recursively before discovery.

    Returns:
        Deduplicated decorated task wrappers matching the configured roots.
    """
    import_task_modules(task_modules)
    import_task_packages(task_packages)

    # Modules imported by the application have already executed their
    # decorators, so the registry is sufficient when no explicit roots were
    # configured. Explicit roots still act as a filter and import boundary.
    module_filters = task_modules + task_packages
    discovered = iter_registered_tasks(module_filters or None)
    deduped: list[Any] = []
    seen: set[int] = set()
    for task_wrapper in discovered:
        identity = id(task_wrapper)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(task_wrapper)
    return deduped


__all__ = ["discover_registered_tasks", "import_task_modules", "import_task_packages"]
