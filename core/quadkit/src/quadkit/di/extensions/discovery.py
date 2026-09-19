"""Convention-over-configuration discovery utilities.

This module provides scanners that discover framework components
by scanning Python namespaces for specific subclasses. Used by
Application.boot() and AutoWiringMixin to auto-wire providers,
controllers, and event handlers without explicit registration.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.provider import Provider

logger = get_logger(__name__)


def _import_namespace(namespace: str) -> list:
    """Import a namespace, returning all modules found.

    If the namespace is a package, imports it and all immediate submodules.
    If the namespace is a module, imports just that module.

    Note: This only scans immediate submodules (depth=1). Nested packages
    like 'myapp.providers.database.pool' are not automatically discovered.
    Use recursive scanning (pkgutil.walk_packages) if deeper scanning is needed.
    """
    modules = []
    try:
        module = importlib.import_module(namespace)
        modules.append(module)

        # If it's a package, also import submodules
        if hasattr(module, "__path__"):
            for _importer, submodule_name, _ispkg in pkgutil.iter_modules(
                module.__path__,
                prefix=f"{namespace}.",
            ):
                try:
                    modules.append(importlib.import_module(submodule_name))
                except (ImportError, ModuleNotFoundError):
                    logger.debug("Failed to import submodule: %s", submodule_name)
    except ImportError:
        logger.warning("Failed to import namespace: %s", namespace)

    return modules


class ProviderScanner:
    """Scans namespaces for Provider subclasses.

    This utility replaces the previous **HandlerScanner** which was
    intended to discover event handlers via type inspection.  That class
    has been removed: the framework now provides a concrete event bus and
    explicit registration, rendering automated handler scanning unnecessary.
    """

    @staticmethod
    def scan(namespace: str) -> list[type[Provider]]:
        """Import a namespace and find all Provider subclasses.

        Args:
            namespace: Dotted Python import path (e.g. 'myapp.providers').

        Returns:
            List of Provider subclass types found in the namespace.
        """
        from quadkit.di.provider import Provider

        seen: set[type] = set()
        found: list[type[Provider]] = []
        for module in _import_namespace(namespace):
            for name in dir(module):
                obj = getattr(module, name, None)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, Provider)
                    and obj is not Provider
                    and obj not in seen
                    and not getattr(obj, "__abstract__", False)
                    and not inspect.isabstract(obj)
                ):
                    seen.add(obj)
                    found.append(obj)

        return found

    @staticmethod
    def instantiate(provider_cls: type[Provider], config: object) -> Provider:
        """Instantiate a discovered provider, injecting config if accepted.

        Tries ``provider_cls.from_config(config)`` first, then falls back to
        calling the constructor with a ``config`` keyword argument when the
        signature accepts one.

        Args:
            provider_cls: The provider class to instantiate.
            config: Application configuration object passed through to the
                provider.  The scanner is agnostic to its concrete type.

        Returns:
            Instantiated provider.
        """
        if hasattr(provider_cls, "from_config") and callable(provider_cls.from_config):
            try:
                return provider_cls.from_config(config)
            except Exception:  # noqa: BLE001 — from_config is best-effort; fall back to __init__ construction
                pass

        sig = inspect.signature(provider_cls.__init__)
        params = {k: v for k, v in sig.parameters.items() if k != "self"}

        if not params:
            return provider_cls()
        if "config" in params:
            return provider_cls(config=config)  # type: ignore[call-arg]

        return provider_cls()


def import_string(dotted_path: str) -> Any:
    """Import a dotted module path and return the attribute at the end.

    E.g. 'the optional provider module' imports 'the optional provider module' and returns
    the 'DatabaseService' attribute.
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        msg = f"'{dotted_path}' is not a valid dotted import path"
        raise ImportError(msg) from err

    module = importlib.import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as err:
        msg = f"Module '{module_path}' has no attribute '{class_name}'"
        raise ImportError(msg) from err


__all__ = [
    "ProviderScanner",
    "import_string",
]
