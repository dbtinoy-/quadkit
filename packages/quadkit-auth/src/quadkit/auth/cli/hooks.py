"""CLI lifecycle hooks for quadkit-auth."""

from __future__ import annotations


def log_auth_command(ctx: object) -> None:
    """Audit-log auth-sensitive CLI commands.

    Args:
        ctx: CLI context with command name and arguments.
    """
