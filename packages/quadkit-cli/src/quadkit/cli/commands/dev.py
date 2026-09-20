"""Development server command using server registry."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from quadkit.cli.output import OutputManager
from quadkit.cli.registry.server import (
    ServerConfig,
    ServerManager,
    ServerRegistry,
    discover_entry_point,
)


def _server_registry() -> ServerRegistry:
    """Fresh default-populated server registry for a command invocation."""
    return ServerRegistry.with_defaults()


from quadkit.cli.runtime import handle_errors

app = typer.Typer(name="dev")


@app.callback(invoke_without_command=True)
@handle_errors
def main(
    entry_point: Annotated[
        str | None,
        typer.Option("--entry", help="Application entry point (e.g., src/main.py)"),
    ] = None,
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload/--no-reload", help="Enable/disable hot reload"),
    ] = True,
    env: Annotated[
        str,
        typer.Option("--env", help="Environment (development/staging/production)"),
    ] = "development",
    server: Annotated[
        str | None,
        typer.Option("--server", help="Server backend (uvicorn, hypercorn, granian)"),
    ] = None,
) -> None:
    """Start development server."""
    out = OutputManager()

    if not entry_point:
        entry_point = discover_entry_point()

    if not entry_point or not Path(entry_point).exists():
        out.error(
            "Could not find application entry point (e.g., src/main.py).",
            hint="Specify it using --entry <path>",
        )
        raise typer.Exit(1)

    server_backend = None
    if server:
        server_backend = _server_registry().get(server)
        if not server_backend:
            out.error(f"Unknown server: {server}")
            out.info(
                f"Available servers: {', '.join(b.name for b in _server_registry().get_available())}",
            )
            raise typer.Exit(1)

    if not server_backend:
        # Prefer granian → uvicorn
        for preferred in ("granian", "uvicorn"):
            b = _server_registry().get(preferred)
            if b and b.is_available():
                server_backend = b
                break
        if not server_backend:
            server_backend = _server_registry().get_default()

    out.print(f"[info]Starting dev server with [bold]{server_backend.name}[/bold]")
    out.print(
        f"[info]Host: [bold]{host}[/bold], Port: [bold]{port}[/bold], Env: [bold]{env}[/bold]",
    )

    config = ServerConfig(
        entry_point=entry_point,
        host=host,
        port=port,
        reload=reload,
        env={"QK_ENV": env},
    )

    manager = ServerManager(server_backend)
    manager.start_dev(config)


@app.command(name="start")
@handle_errors
def start(
    entry_point: Annotated[
        str | None,
        typer.Option("--entry", help="Application entry point (e.g., src/main.py)"),
    ] = None,
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = "0.0.0.0",  # noqa: S104 — dev server default, operator overridable
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = 8000,
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", help="Number of worker processes"),
    ] = 1,
    env: Annotated[
        str,
        typer.Option("--env", help="Environment (development/staging/production)"),
    ] = "production",
    server: Annotated[
        str | None,
        typer.Option("--server", help="Server backend (uvicorn, hypercorn, granian)"),
    ] = None,
) -> None:
    """Start production server."""
    out = OutputManager()

    if not entry_point:
        entry_point = discover_entry_point()

    if not entry_point or not Path(entry_point).exists():
        out.error(
            "Could not find application entry point (e.g., src/main.py).",
            hint="Specify it using --entry <path>",
        )
        raise typer.Exit(1)

    server_backend = None
    if server:
        server_backend = _server_registry().get(server)
        if not server_backend:
            out.error(f"Unknown server: {server}")
            out.info(
                f"Available servers: {', '.join(b.name for b in _server_registry().get_available())}",
            )
            raise typer.Exit(1)

    if not server_backend:
        # Prefer granian → uvicorn
        for preferred in ("granian", "uvicorn"):
            b = _server_registry().get(preferred)
            if b and b.is_available():
                server_backend = b
                break
        if not server_backend:
            server_backend = _server_registry().get_default()

    out.print(
        f"[info]Starting production server with [bold]{server_backend.name}[/bold]",
    )
    out.print(
        f"[info]Host: [bold]{host}[/bold], Port: [bold]{port}[/bold], Workers: [bold]{workers}[/bold], Env: [bold]{env}[/bold]",
    )

    config = ServerConfig(
        entry_point=entry_point,
        host=host,
        port=port,
        workers=workers,
        env={"QK_ENV": env},
    )

    manager = ServerManager(server_backend)
    manager.start(config)


__all__ = ["app"]
