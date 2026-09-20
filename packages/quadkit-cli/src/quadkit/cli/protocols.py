"""CLI command protocols.

This module defines protocols for CLI command implementations.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CommandProtocol(Protocol):
    """Protocol for CLI command implementations."""

    def execute(self, args: list[str], options: dict[str, Any]) -> int:
        """Execute the command.

        Args:
            args: Positional arguments
            options: Parsed options dictionary

        Returns:
            Exit code (0 for success)
        """
        ...

    @property
    def name(self) -> str:
        """Command name."""
        ...

    @property
    def description(self) -> str:
        """Command description."""
        ...

    def get_help(self) -> str:
        """Get help text for the command.

        Returns:
            Help text
        """
        ...


@runtime_checkable
class CLIRunnerProtocol(Protocol):
    """Protocol for objects that can run CLI commands.

    A ``CLIRunner`` discovers registered :class:`CommandProtocol` implementations
    and dispatches invocations based on the command name.  Implementations may
    wrap Click, Typer, argparse, or any other CLI framework.
    """

    def run(self, argv: list[str] | None = None) -> int:
        """Parse *argv* (or ``sys.argv``) and dispatch to the matching command.

        Args:
            argv: Argument vector to parse.  Defaults to ``sys.argv[1:]``.

        Returns:
            Exit code (0 for success, non-zero for failure).
        """
        ...

    def register_command(self, command: CommandProtocol) -> None:
        """Register a command with this runner.

        Args:
            command: A :class:`CommandProtocol` implementation to register.
        """
        ...


@runtime_checkable
class CLIApplicationProtocol(Protocol):
    """Protocol for a top-level CLI application.

    A ``CLIApplication`` owns a :class:`CLIRunnerProtocol` and manages the
    full lifecycle of a CLI process: configuration loading, provider boot,
    command dispatch, and shutdown.
    """

    @property
    def runner(self) -> CLIRunnerProtocol:
        """The underlying command runner."""
        ...

    async def boot(self) -> None:
        """Start the application, boot providers, and prepare for dispatch."""
        ...

    async def shutdown(self) -> None:
        """Tear down resources and exit cleanly."""
        ...


__all__ = ["CLIApplicationProtocol", "CLIRunnerProtocol", "CommandProtocol"]
