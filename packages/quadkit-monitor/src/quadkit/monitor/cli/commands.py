"""Monitor CLI command group factory."""

from __future__ import annotations

import typer


def create_monitor_app() -> typer.Typer:
    """Create the `quadkit monitor` command group.

    Returns:
        A Typer app containing monitoring subcommands.
    """
    app = typer.Typer(help="Observability and monitoring commands")

    metrics_app = typer.Typer(help="Metrics management")
    app.add_typer(metrics_app, name="metrics")

    slo_app = typer.Typer(help="SLO management")
    app.add_typer(slo_app, name="slo")

    alerts_app = typer.Typer(help="Alert management")
    app.add_typer(alerts_app, name="alerts")

    @app.command("status")
    def status() -> None:
        """Show monitoring backend status."""
        typer.echo("Monitoring status not yet implemented")

    @metrics_app.command("list")
    def metrics_list(
        category: str | None = typer.Option(
            None, "--category", help="Filter by category"
        ),
    ) -> None:
        """List registered metrics."""
        typer.echo("Metrics listing not yet implemented")

    @slo_app.command("status")
    def slo_status(
        name: str | None = typer.Argument(None, help="SLO name to check"),
    ) -> None:
        """Show SLO compliance status."""
        typer.echo("SLO status not yet implemented")

    @alerts_app.command("list")
    def alerts_list(
        active_only: bool = typer.Option(
            False, "--active", help="Show only active alerts"
        ),
    ) -> None:
        """List configured alerts."""
        typer.echo("Alert listing not yet implemented")

    return app
