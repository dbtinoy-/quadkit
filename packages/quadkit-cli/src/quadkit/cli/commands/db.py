"""Database management commands using registry pattern.

The Typer application is assembled here; command implementations live in
grouped sibling modules and are registered below in legacy help-listing
order so the CLI surface stays byte-identical.
"""

from __future__ import annotations

import typer

from quadkit.cli.commands.db_commands_data import reset, seed, setup
from quadkit.cli.commands.db_commands_migrations import (
    create,
    downgrade,
    history,
    init,
    migrate,
    status,
    upgrade,
    validate,
)
from quadkit.cli.commands.db_commands_ops import backup, inspect_, restore, shell

app = typer.Typer(name="db")

app.command()(init)
app.command()(migrate)
app.command()(create)
app.command()(upgrade)
app.command()(downgrade)
app.command()(status)
app.command()(history)
app.command()(validate)
app.command()(seed)
app.command()(reset)
app.command(name="shell")(shell)
app.command(name="inspect")(inspect_)
app.command(name="backup")(backup)
app.command(name="restore")(restore)
app.command()(setup)

__all__ = ["app"]
