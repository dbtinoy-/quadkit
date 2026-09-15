"""Lazy loading utilities for deferred initialization of services and components."""

from __future__ import annotations

from typing import Any


class LazyImport:
    """Lazy import that defers module loading until first access.

    This helps reduce startup time by only importing modules when they're actually used.

    Example:
        ```python
        # Create lazy import
        pandas = LazyImport("pandas")

        # Module not imported yet
        # ...

        # Module imported on first use
        df = pandas.DataFrame(data)
        ```
    """

    def __init__(self, module_name: str):
        """Initialize lazy import.

        Args:
            module_name: Fully qualified module name to import
        """
        self._module_name = module_name
        self._module: Any = None
        self._initialized = False

    def _ensure_initialized(self) -> Any:
        """Ensure the module is imported."""
        if not self._initialized:
            import importlib

            self._module = importlib.import_module(self._module_name)
            self._initialized = True
        return self._module

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the module."""
        if name in ("_module_name", "_module", "_initialized", "_ensure_initialized"):
            return object.__getattribute__(self, name)
        module = self._ensure_initialized()
        return getattr(module, name)

    def __repr__(self) -> str:
        """String representation."""
        if self._initialized:
            return f"LazyImport({self._module_name!r}, loaded)"
        return f"LazyImport({self._module_name!r}, not loaded)"

    def is_initialized(self) -> bool:
        """Check if the module has been imported.

        Returns:
            True if module has been loaded
        """
        return self._initialized


__all__ = ["LazyImport"]
