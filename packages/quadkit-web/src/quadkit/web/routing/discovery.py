"""Controller auto-discovery utilities for ``quadkit.web.routing``.

Scans Python packages and modules for ``ControllerProtocol`` subclasses,
enabling convention-based composition roots in web applications.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)


def discover_controllers(packages: tuple[str, ...] | list[str]) -> list[type]:
    """Scan packages for Controller subclasses and return the classes.

    Args:
        packages: Dotted Python package paths to scan.

    Returns:
        List of Controller subclasses (not instantiated — the DI container
        constructs them during boot).
    """
    from quadkit.contracts.web.controller import ControllerProtocol

    found: list[type] = []
    seen: set[type] = set()

    for pkg in packages:
        for cls in _scan_subclasses(pkg, ControllerProtocol):
            if cls in seen:
                continue
            seen.add(cls)
            found.append(cls)
            logger.debug("discovery.controller.found", controller=cls.__name__)

    return found


def discover_websocket_handlers(packages: tuple[str, ...] | list[str]) -> list[type]:
    """Scan packages for classes marked with ``@websocket_handler``.

    WebSocket handlers are deliberately discovered separately from HTTP
    controllers: they have a class-level path marker and are mounted as
    Starlette ``WebSocketRoute`` instances rather than HTTP routes.

    Args:
        packages: Dotted Python package paths to scan.

    Returns:
        Deduplicated handler classes in discovery order.
    """
    found: list[type] = []
    seen: set[type] = set()

    for pkg in packages:
        for cls in _scan_marked_classes(pkg, "_is_websocket_handler"):
            if cls in seen:
                continue
            seen.add(cls)
            found.append(cls)
            logger.debug("discovery.websocket.found", handler=cls.__name__)

    return found


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
        except (ImportError, ModuleNotFoundError, AttributeError) as error:
            logger.debug(
                "discovery.module.import_failed", module=modname, error=str(error)
            )

    results.extend(_collect_subclasses(root, base))
    return results


def _scan_marked_classes(package: str, marker: str) -> list[type]:
    """Walk *package* and collect classes carrying a truthy *marker*."""
    results: list[type] = []

    try:
        root = importlib.import_module(package)
    except ImportError:
        logger.debug("discovery.package.import_failed", package=package)
        return results

    root_path = getattr(root, "__path__", None)
    if root_path is None:
        results.extend(_collect_marked_classes(root, marker))
        return results

    for _finder, modname, _ispkg in pkgutil.walk_packages(
        root_path,
        prefix=package + ".",
        onerror=lambda name: logger.debug("discovery.walk.error", module=name),
    ):
        try:
            module = importlib.import_module(modname)
            results.extend(_collect_marked_classes(module, marker))
        except (ImportError, ModuleNotFoundError, AttributeError) as error:
            logger.debug(
                "discovery.module.import_failed", module=modname, error=str(error)
            )

    results.extend(_collect_marked_classes(root, marker))
    return results


def _collect_marked_classes(module: Any, marker: str) -> list[type]:
    """Collect classes defined in *module* carrying a truthy *marker*."""
    results: list[type] = []
    for attr_name in dir(module):
        try:
            obj = getattr(module, attr_name)
        except (AttributeError, TypeError) as error:
            logger.debug(
                "discovery.getattr_failed",
                module=module.__name__,
                attr=attr_name,
                error=str(error),
            )
            continue
        if (
            isinstance(obj, type)
            and getattr(obj, marker, False) is True
            and obj.__module__ == module.__name__
        ):
            results.append(obj)
    return results


def _collect_subclasses(module: Any, base: type) -> list[type]:
    """Collect all concrete subclasses of *base* defined in *module*."""
    results: list[type] = []
    for attr_name in dir(module):
        try:
            obj = getattr(module, attr_name)
        except (AttributeError, TypeError) as error:
            logger.debug(
                "discovery.getattr_failed",
                module=module.__name__,
                attr=attr_name,
                error=str(error),
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


__all__ = ["discover_controllers", "discover_websocket_handlers"]
