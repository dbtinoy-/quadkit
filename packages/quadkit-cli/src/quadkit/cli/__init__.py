"""Quadkit CLI - Command-line tools for Quadkit Framework."""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.cli.constants import __version__ as __version__

if TYPE_CHECKING:
    from typer import Argument, Exit, Option, echo
    from typer import Typer as CLIApp
    from typer.testing import CliRunner

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
    "Argument": ("typer", "Argument"),
    "CLIApp": ("typer", "Typer"),
    "CLIApplicationProtocol": ("quadkit.cli.protocols", "CLIApplicationProtocol"),
    "CLIConfig": ("quadkit.cli.config", "CLIConfig"),
    "CLIContext": ("quadkit.cli.runtime", "CLIContext"),
    "CLIModule": ("quadkit.cli.module", "CLIModule"),
    "CLIRunnerProtocol": ("quadkit.cli.protocols", "CLIRunnerProtocol"),
    "CliError": ("quadkit.cli.exceptions", "CliError"),
    "CliRunner": ("typer.testing", "CliRunner"),
    "CommandProtocol": ("quadkit.cli.protocols", "CommandProtocol"),
    "ConfigNotFoundError": ("quadkit.cli.exceptions", "ConfigNotFoundError"),
    "Exit": ("typer", "Exit"),
    "Option": ("typer", "Option"),
    "ProviderNotInstalledError": (
        "quadkit.cli.exceptions",
        "ProviderNotInstalledError",
    ),
    "OutputManager": ("quadkit.cli.output", "OutputManager"),
    "echo": ("typer", "echo"),
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
    "Argument",
    "CLIApp",
    "CLIApplicationProtocol",
    "CLIConfig",
    "CLIContext",
    "CLIModule",
    "CLIRunnerProtocol",
    "CliError",
    "CliRunner",
    "CommandProtocol",
    "ConfigNotFoundError",
    "Exit",
    "Option",
    "OutputManager",
    "ProviderNotInstalledError",
    "echo",
    "find_config",
    "handle_errors",
    "load_config_yaml",
]
