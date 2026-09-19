"""Provider and controller auto-discovery utilities.

Scans Python packages and modules for Provider and Controller subclasses,
enabling convention-based composition roots.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import inspect
from pathlib import Path
import pkgutil
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.provider import Provider

logger = get_logger(__name__)

_PROVIDER_ATTR = "__quadkit_provider__"


def discover_providers(packages: tuple[str, ...] | list[str]) -> list[Provider]:
    """Scan packages for Provider subclasses and return instantiated providers.

    Only providers with a no-argument ``__init__`` (or whose only ``__init__``
    params have defaults) are auto-instantiated. Providers requiring explicit
    constructor arguments are skipped with a debug log.

    Args:
        packages: Dotted Python package paths to scan (e.g. ``("my_app.modules",)``).

    Returns:
        List of instantiated Provider objects, one per discovered subclass.
    """
    from quadkit.di.provider import Provider

    found: list[Provider] = []
    seen: set[type] = set()

    for pkg in packages:
        for cls in _scan_subclasses(pkg, Provider):
            if cls in seen:
                continue
            seen.add(cls)
            try:
                instance = cls()
                found.append(instance)
                logger.debug("discovery.provider.found", provider=cls.__name__)
            except Exception:  # noqa: BLE001 — a provider that cannot be instantiated without args is skipped, never a discovery failure
                logger.debug(
                    "discovery.provider.skipped",
                    provider=cls.__name__,
                    reason="instantiation_failed",
                )

    return found


def discover_injectables(
    packages: tuple[str, ...] | list[str],
) -> list[tuple[type, Any]]:
    """Scan packages for ``@injectable`` / ``@singleton`` decorated classes.

    Returns a list of ``(class, scope)`` pairs ready for auto-registration
    into a DI container.

    Args:
        packages: Dotted Python package paths to scan.

    Returns:
        List of ``(cls, ServiceScope)`` tuples for all decorated classes.
    """
    from quadkit.di.decorators import INJECTABLE_ATTR

    results: list[tuple[type, Any]] = []
    seen: set[type] = set()

    for pkg in packages:
        try:
            root = importlib.import_module(pkg)
        except ImportError:
            logger.debug("discovery.package.import_failed", package=pkg)
            continue

        root_path = getattr(root, "__path__", None)
        modules_to_scan: list[Any] = [root]

        if root_path is not None:
            for _finder, modname, _ispkg in pkgutil.walk_packages(
                root_path,
                prefix=pkg + ".",
                onerror=lambda name: logger.debug("discovery.walk.error", module=name),
            ):
                try:
                    modules_to_scan.append(importlib.import_module(modname))
                except (ImportError, ModuleNotFoundError, AttributeError) as e:
                    logger.debug(
                        "discovery.module.import_failed", module=modname, error=str(e)
                    )

        for module in modules_to_scan:
            for attr_name in dir(module):
                try:
                    obj = getattr(module, attr_name)
                except (AttributeError, TypeError) as e:
                    logger.debug(
                        "discovery.getattr_failed",
                        module=module.__name__,
                        attr=attr_name,
                        error=str(e),
                    )
                    continue
                if not (
                    isinstance(obj, type)
                    and obj.__module__ == module.__name__
                    and obj not in seen
                ):
                    continue
                meta = getattr(obj, INJECTABLE_ATTR, None)
                if meta is not None:
                    seen.add(obj)
                    results.append((obj, meta.get("scope")))
                    logger.debug(
                        "discovery.injectable.found",
                        cls=obj.__name__,
                        scope=meta.get("scope"),
                    )

    return results


def _scan_subclasses(package: str, base: type) -> list[type]:
    """Walk a package tree and collect all non-abstract subclasses of *base*.

    Args:
        package: Dotted package path to scan.
        base: Base class to match against.

    Returns:
        List of concrete subclasses found.
    """
    results: list[type] = []

    try:
        root = importlib.import_module(package)
    except ImportError:
        logger.debug("discovery.package.import_failed", package=package)
        return results

    root_path = getattr(root, "__path__", None)
    if root_path is None:
        # It's a module, not a package — scan it directly
        results.extend(_collect_subclasses(root, base))
        return results

    for _finder, modname, _ispkg in pkgutil.walk_packages(
        root_path,
        prefix=package + ".",
        onerror=lambda name: logger.debug("discovery.walk.error", module=name),
    ):
        try:
            module = importlib.import_module(modname)
            results.extend(_collect_subclasses(module, base))
        except (ImportError, ModuleNotFoundError, AttributeError) as e:
            logger.debug("discovery.module.import_failed", module=modname, error=str(e))

    # Also scan the root module itself
    results.extend(_collect_subclasses(root, base))
    return results


def _collect_subclasses(module: Any, base: type) -> list[type]:
    """Collect all concrete subclasses of *base* defined in *module*."""
    results: list[type] = []
    for attr_name in dir(module):
        try:
            obj = getattr(module, attr_name)
        except (AttributeError, TypeError) as e:
            logger.debug(
                "discovery.getattr_failed",
                module=module.__name__,
                attr=attr_name,
                error=str(e),
            )
            continue
        if (
            isinstance(obj, type)
            and issubclass(obj, base)
            and obj is not base
            and obj.__module__ == module.__name__
        ):
            results.append(obj)
    return results


__all__ = [
    "discover_injectables",
    "discover_modules_from_directories",
    "discover_modules_from_entry_points",
    "discover_providers",
]


def discover_modules_from_entry_points(
    group: str = "quadkit.modules",
) -> dict[str, type]:
    """Discover Module subclasses registered via importlib.metadata entry points.

    Scans the given entry-point group and returns all entries that resolve
    to a concrete Module subclass. Entries that fail to load or do not
    resolve to a Module subclass are skipped with a warning log.

    Args:
        group: Entry-point group name. Default "quadkit.modules".

    Returns:
        Dict mapping entry-point name to Module class.
    """
    from quadkit.di.module import Module

    discovered: dict[str, type[Module]] = {}
    for ep in importlib.metadata.entry_points(group=group):
        try:
            obj = ep.load()
        except Exception:  # noqa: BLE001
            logger.warning(
                "module_discovery_entry_point_load_failed",
                group=group,
                name=ep.name,
            )
            continue
        if isinstance(obj, type) and issubclass(obj, Module) and obj is not Module:
            discovered[ep.name] = obj
        else:
            logger.debug(
                "module_discovery_entry_point_not_a_module",
                group=group,
                name=ep.name,
                loaded=repr(obj),
            )
    return discovered


def discover_modules_from_directories(
    directories: list[str | Path],
) -> dict[str, type]:
    """Discover Module subclasses from filesystem directories.

    Scans each directory for a ``plugin.py`` or ``__init__.py`` file,
    loads it, and extracts any Module subclasses defined in it.
    Files that fail to load or contain no Module subclasses are skipped.

    Args:
        directories: List of filesystem paths to scan.

    Returns:
        Dict mapping class name to Module class.
    """
    from quadkit.di.module import Module

    discovered: dict[str, type[Module]] = {}

    for directory in directories:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            logger.debug("module_discovery_dir_skipped", path=str(path))
            continue

        for candidate in ("plugin.py", "__init__.py"):
            file_path = path / candidate
            if not file_path.exists():
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"_quadkit_discovery_{path.name}", file_path
                )
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "module_discovery_dir_load_failed",
                    file=str(file_path),
                )
                continue

            for _name, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, Module)
                    and obj is not Module
                    and obj.__module__ == mod.__name__
                ):
                    discovered[obj.__name__] = obj
            break  # only process first candidate found per directory

    return discovered
