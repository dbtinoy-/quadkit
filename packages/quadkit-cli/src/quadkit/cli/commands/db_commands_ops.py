"""Backup, restore, shell, and inspection commands for the db command group."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
import subprocess

import typer

from quadkit.cli.output import OutputManager
from quadkit.cli.registry import DatabaseConnection
from quadkit.cli.runtime import handle_errors


@handle_errors
def shell(
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Open database shell (auto-detects database type)."""
    out = OutputManager()

    try:
        conn = DatabaseConnection()
        backend = conn.backend

        client_binary = backend.get_client_binary()
        if not client_binary:
            backend_name = backend.name
            out.error(
                f"Client for '{backend_name}' not found.",
                hint=f"Install the {backend_name} client (e.g., sudo apt install {backend_name}-client)",
            )
            raise typer.Exit(1)

        out.info(f"Opening {backend.name} shell...")
        conn.open_shell()

    except Exception as e:  # noqa: BLE001 — any shell failure is a CLI error
        out.error(f"Failed to open shell: {e}")
        raise typer.Exit(1) from None


@handle_errors
def inspect_(
    table: str | None = typer.Option(
        None, "--table", "-t", help="Specific table to inspect"
    ),
    env: str | None = typer.Option(None, "--env", "-e", help="Environment name"),
) -> None:
    """Show database schema."""
    out = OutputManager()

    async def _run() -> None:
        try:
            conn = DatabaseConnection()

            async with conn:
                if table:
                    columns = await conn.get_columns(table)
                    out.print(f"[bold]Columns in {table}:[/bold]")
                    rows = [
                        [col["name"], col["type"], str(col.get("default", ""))]
                        for col in columns
                    ]
                    out.table(["Column", "Type", "Default"], rows)
                else:
                    tables = await conn.get_tables()
                    if not tables:
                        out.info("No tables found in database.")
                        return
                    out.print("[bold]Tables:[/bold]")
                    for t in tables:
                        out.print(f"  - {t}")

                    out.print("\n[bold]Schema Details:[/bold]")
                    for t in tables:
                        columns = await conn.get_columns(t)
                        out.print(f"\n[cyan]{t}[/cyan]")
                        rows = [
                            [
                                col["name"],
                                col["type"],
                                "YES" if col["nullable"] else "NO",
                            ]
                            for col in columns
                        ]
                        out.table(["Column", "Type", "Nullable"], rows)

        except ImportError as e:
            out.error(f"quadkit-sql not installed: {e}")
            out.info("Install with: pip install quadkit-sql")
            raise typer.Exit(1) from None
        except Exception as e:  # noqa: BLE001 — any inspect failure is a CLI error
            out.error(f"Failed to inspect database: {e}")
            raise typer.Exit(1) from None

    asyncio.run(_run())


@handle_errors
def backup(
    output: str | None = typer.Option("--output", "-o", help="Output file path"),
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Backup the database."""
    out = OutputManager()

    try:
        conn = DatabaseConnection()
        backend = conn.backend

        client_binary = backend.get_client_binary()
        if not client_binary:
            backend_name = backend.name
            out.error(f"Backup not supported for {backend_name}")
            raise typer.Exit(1)

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        default_output = f"backup_{backend.name}_{timestamp}.sql"
        output_path = output or default_output

        try:
            # Use registry pattern to build backup command
            cmd = backend.build_backup_command(conn.params, output_path)
            out.info(f"Backing up {backend.name} database to {output_path}...")

            subprocess.run(  # noqa: S603 — registry-built argv list
                cmd,
                check=True,
                env=backend.subprocess_env(conn.params),
            )
            out.success(f"Database backed up to {output_path}")
        except subprocess.CalledProcessError as e:
            out.error(f"Backup failed: {e}")
            raise typer.Exit(1) from None
        except RuntimeError as e:
            out.error(str(e))
            raise typer.Exit(1) from None

    except Exception as e:  # noqa: BLE001 — any backup failure is a CLI error
        out.error(f"Failed to backup database: {e}")
        raise typer.Exit(1) from None


@handle_errors
def restore(
    input_path: str = typer.Argument(..., help="Backup file to restore"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force restore without confirmation",
    ),
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Restore the database from backup."""
    out = OutputManager()
    if not force:
        confirm = typer.confirm(
            "Are you sure you want to restore the database? This will overwrite all data.",
        )
        if not confirm:
            raise typer.Abort

    backup_path = Path(input_path)
    if not backup_path.exists():
        out.error(f"Backup file not found: {input_path}")
        raise typer.Exit(1)

    try:
        conn = DatabaseConnection()
        backend = conn.backend

        client_binary = backend.get_client_binary()
        if not client_binary:
            backend_name = backend.name
            out.error(f"Restore not supported for {backend_name}")
            raise typer.Exit(1)

        # Use registry pattern to build restore command
        cmd = backend.build_restore_command(conn.params, input_path)

        out.info(f"Restoring {backend.name} database from {input_path}...")

        with open(input_path) as f:
            subprocess.run(  # noqa: S603 — registry-built argv list
                cmd,
                stdin=f,
                check=True,
                env=backend.subprocess_env(conn.params),
            )

        out.success(f"Database restored from {input_path}")

    except subprocess.CalledProcessError as e:
        out.error(f"Restore failed: {e}")
        raise typer.Exit(1) from None
    except Exception as e:  # noqa: BLE001 — any restore failure is a CLI error
        out.error(f"Failed to restore database: {e}")
        raise typer.Exit(1) from None


__all__ = ["backup", "inspect_", "restore", "shell"]
