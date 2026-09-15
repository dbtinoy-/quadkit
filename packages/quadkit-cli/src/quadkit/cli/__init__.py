"""Quadkit CLI - Command-line tools for Quadkit Framework."""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.cli.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.cli.config import CLIConfig
    from quadkit.cli.exceptions import (
        CliError,
        ConfigNotFoundError,
        ProviderNotInstalledError,
    )
    from quadkit.cli.lib import (
        find_config,
        load_config_yaml,
    )
    from quadkit.cli.output import OutputManager
    from quadkit.cli.protocols import (
        CLIApplicationProtocol,
        CLIRunnerProtocol,
        CommandProtocol,
    )
    from quadkit.cli.runtime import (
        CLIContext,
        handle_errors,
    )

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "CLIApplicationProtocol": ("quadkit.cli.protocols", "CLIApplicationProtocol"),
    "CLIConfig": ("quadkit.cli.config", "CLIConfig"),
    "CLIContext": ("quadkit.cli.runtime", "CLIContext"),
    "CLIModule": ("quadkit.cli.module", "CLIModule"),
    "CLIRunnerProtocol": ("quadkit.cli.protocols", "CLIRunnerProtocol"),
    "CliError": ("quadkit.cli.exceptions", "CliError"),
    "CommandProtocol": ("quadkit.cli.protocols", "CommandProtocol"),
    "ConfigNotFoundError": ("quadkit.cli.exceptions", "ConfigNotFoundError"),
    "ProviderNotInstalledError": (
        "quadkit.cli.exceptions",
        "ProviderNotInstalledError",
    ),
    "OutputManager": ("quadkit.cli.output", "OutputManager"),
    "handle_errors": ("quadkit.cli.runtime", "handle_errors"),
    "find_config": ("quadkit.cli.lib", "find_config"),
    "load_config_yaml": ("quadkit.cli.lib", "load_config_yaml"),
}


def __getattr__(name: str) -> Any:
    """Lazy load attributes to avoid circular imports."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """List available attributes for IDE support."""
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = [
    "CLIApplicationProtocol",
    "CLIConfig",
    "CLIContext",
    "CLIModule",
    "CLIRunnerProtocol",
    "CliError",
    "CommandProtocol",
    "ConfigNotFoundError",
    "OutputManager",
    "ProviderNotInstalledError",
    "find_config",
    "handle_errors",
    "load_config_yaml",
]
