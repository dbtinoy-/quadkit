"""OutputManager — unified output for all CLI commands.

Supports three modes:
- Default: Rich-formatted human-readable output
- JSON: Machine-readable JSON to stdout
- Quiet: Suppress non-error output
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table
from rich.theme import Theme

from quadkit.serialization import dumps_str

if TYPE_CHECKING:
    from quadkit.cli.exceptions import CliError

#: Markup styles every CLI output manager renders with, as immutable data.
_STYLES: tuple[tuple[str, str], ...] = (
    ("info", "cyan"),
    ("warning", "yellow"),
    ("error", "bold red"),
    ("success", "bold green"),
    ("hint", "dim cyan"),
)


class OutputManager:
    """Unified output manager for all CLI commands."""

    def __init__(
        self,
        *,
        json_mode: bool = False,
        quiet: bool = False,
        debug: bool = False,
        no_color: bool = False,
    ) -> None:
        self.json_mode = json_mode
        self.quiet = quiet
        self.debug = debug
        self.console = Console(
            theme=Theme(dict(_STYLES)),
            no_color=no_color,
            stderr=False,
        )

    def success(self, message: str, data: dict[str, Any] | None = None) -> None:
        """Print a success message."""
        if self.json_mode:
            payload: dict[str, Any] = {"status": "success", "message": message}
            if data:
                payload["data"] = data
            print(dumps_str(payload))
            return
        if self.quiet:
            return
        self.console.print(f"[success]{message}[/success]")

    def error(self, message: str, hint: str | None = None) -> None:
        """Print an error message. Shown even in quiet mode."""
        if self.json_mode:
            payload: dict[str, Any] = {"status": "error", "message": message}
            if hint:
                payload["hint"] = hint
            print(dumps_str(payload))
            return
        self.console.print(f"[error]Error:[/error] {message}", highlight=False)
        if hint:
            self.console.print(f"  [hint]{hint}[/hint]")

    def warning(self, message: str) -> None:
        """Print a warning message."""
        if self.json_mode:
            print(dumps_str({"status": "warning", "message": message}))
            return
        if self.quiet:
            return
        self.console.print(f"[warning]Warning:[/warning] {message}")

    def info(self, message: str) -> None:
        """Print an informational message."""
        if self.json_mode or self.quiet:
            return
        self.console.print(f"[info]{message}[/info]")

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        """Print tabular data."""
        if self.json_mode:
            result = [dict(zip(headers, row, strict=False)) for row in rows]
            print(dumps_str(result))
            return
        if self.quiet:
            return
        t = Table()
        for h in headers:
            t.add_column(h)
        for row in rows:
            t.add_row(*row)
        self.console.print(t)

    def key_value(self, data: dict[str, Any]) -> None:
        """Print key-value pairs."""
        if self.json_mode:
            print(dumps_str(data))
            return
        if self.quiet:
            return
        for k, v in data.items():
            self.console.print(f"[bold]{k}:[/bold] {v}")

    def cli_error(self, err: CliError) -> None:
        """Render a structured CLIError with causes and suggestions."""
        if self.json_mode:
            payload = {
                "status": "error",
                "message": err.message,
                "code": err.code,
                "causes": err.causes,
                "suggestions": err.suggestions,
            }
            print(dumps_str(payload))
            return
        parts = [f"[error]Error:[/error] {err.message}"]
        if err.causes:
            parts.append("")
            parts.append("  [bold]Possible causes:[/bold]")
            for cause in err.causes:
                parts.append(f"    - {cause}")
        if err.suggestions:
            parts.append("")
            parts.append("  [bold]Try:[/bold]")
            for suggestion in err.suggestions:
                parts.append(f"    - {suggestion}")
        self.console.print("\n".join(parts), highlight=False)

    def debug_msg(self, message: str) -> None:
        """Print a debug message (only shown in debug mode)."""
        if not self.debug:
            return
        if self.json_mode:
            print(dumps_str({"level": "debug", "message": message}))
            return
        self.console.print(f"[dim]DEBUG: {message}[/dim]")

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Pass-through to Rich console.print for one-off needs."""
        if self.quiet:
            return
        self.console.print(*args, **kwargs)


__all__ = ["OutputManager"]
