"""Configuration for automatic module discovery."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModuleDiscoveryConfig:
    """Configuration for auto-discovery of Quadkit modules.

    Controls entry-point scanning and filesystem scanning for
    ``Application.discover_modules()``.
    """

    entry_point_group: str = "quadkit.modules"
    """importlib.metadata entry-point group to scan."""

    directories: list[str] = field(default_factory=list)
    """Filesystem directories to scan for Module subclasses."""

    enabled_modules: list[str] = field(default_factory=list)
    """Allowlist of module names (empty = all)."""

    disabled_modules: list[str] = field(default_factory=list)
    """Denylist of module names to skip."""

    auto_discover: bool = False
    """If True, Application calls discover_modules() automatically at start()."""


__all__ = ["ModuleDiscoveryConfig"]
