"""Error handler decorator for CLI commands."""

from __future__ import annotations

from collections.abc import Callable
import functools
from typing import Any, TypeVar

import typer

from quadkit.cli.exceptions import CliError
from quadkit.cli.output.manager import OutputManager

F = TypeVar("F", bound=Callable[..., Any])


def handle_errors(func: F) -> F:
    """Decorator that catches exceptions and renders friendly CLI errors.

    Wraps a Typer command function to catch CliError (renders with
    causes/suggestions) and unexpected exceptions (renders with traceback
    hint).
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except typer.Exit:
            raise
        except CliError as e:
            out = OutputManager()
            out.cli_error(e)
            raise typer.Exit(1) from e
        except Exception as e:
            out = OutputManager()
            out.error(str(e), hint="Run with --debug for full traceback")
            raise typer.Exit(1) from e

    return wrapper  # type: ignore[return-value]


__all__ = ["handle_errors"]
