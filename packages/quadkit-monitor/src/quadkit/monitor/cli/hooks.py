"""CLI lifecycle hooks for quadkit-monitor."""

from __future__ import annotations


def record_command_metric(ctx: object) -> None:
    """Record a metric for every CLI command executed.

    Args:
        ctx: CLI context with command name and arguments.
    """
