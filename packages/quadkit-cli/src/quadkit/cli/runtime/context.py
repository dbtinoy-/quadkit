"""CLI context — shared state for all commands."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.cli.exceptions import CliError
from quadkit.cli.output.manager import OutputManager

if TYPE_CHECKING:
    from pathlib import Path


class CLIContext:
    """Shared context object passed through Typer to all commands.

    Holds the OutputManager, loaded config, and global flag state.
    """

    def __init__(
        self,
        *,
        json_mode: bool = False,
        quiet: bool = False,
        debug: bool = False,
        no_color: bool = False,
        config_path: Path | None = None,
    ) -> None:
        self.json_mode = json_mode
        self.quiet = quiet
        self.debug = debug
        self.no_color = no_color
        self._config_path = config_path
        self._config_data: dict[str, Any] | None = None
        self.output = OutputManager(
            json_mode=json_mode,
            quiet=quiet,
            debug=debug,
            no_color=no_color,
        )

    async def load_config_data(self) -> dict[str, Any]:
        """Lazily load and return config data asynchronously."""
        if self._config_data is None:
            # Deferred (plans/09172026 C-03): the config-loader chain
            # (aiofiles, jinja2 via cli.lib) is only needed once a config
            # is actually loaded, not on every CLI context construction.
            from quadkit.cli.lib.config_loader import (
                find_config,
                load_config_yaml_async,
            )

            path = find_config(explicit_path=self._config_path)
            self._config_data = await load_config_yaml_async(path)
        return self._config_data

    @property
    def config_data(self) -> dict[str, Any]:
        """Lazily load and return the config data for synchronous call sites."""
        if self._config_data is None:
            try:
                self._config_data = asyncio.run(self.load_config_data())
            except RuntimeError as error:
                raise CliError(
                    "Cannot access config_data while an event loop is running",
                    causes=[str(error)],
                    suggestions=["Use `await ctx.load_config_data()` in async code"],
                ) from error
        return self._config_data

    def require_config(self) -> dict[str, Any]:
        """Load config, raising ConfigNotFoundError if absent."""
        return self.config_data


__all__ = ["CLIContext"]
