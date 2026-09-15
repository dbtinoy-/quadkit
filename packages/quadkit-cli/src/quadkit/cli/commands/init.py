"""quadkit init — initialize Quadkit in an existing project."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from quadkit.cli.output import OutputManager
from quadkit.cli.runtime import handle_errors

app = typer.Typer()

_MINIMAL_CONFIG = """\
# Quadkit configuration (validated by QuadkitConfig).
app_name: {project_name}
debug: false
env: development

logging:
  level: INFO
"""

_FULL_CONFIG = """\
# Quadkit configuration (validated by QuadkitConfig plus the
# `quadkit.config` entry-point models).
app_name: {project_name}
debug: false
env: development

logging:
  level: INFO
  json_format: false

modules: []
discovery:
  auto_discover: false
  entry_point_group: quadkit.modules

web:
  server:
    host: "${{WEB_HOST:127.0.0.1}}"
    port: "${{WEB_PORT:8000}}"
  api_docs:
    enabled: true

sql:
  enabled: true
  backend:
    url: "${{DATABASE_URL:sqlite:///./dev.db}}"
  pool:
    min_size: 1
    max_size: 5

auth:
  secret_key: "${{AUTH_SECRET_KEY:change-me-in-production}}"
"""


@app.callback(invoke_without_command=True)
@handle_errors
def init(
    minimal: Annotated[
        bool,
        typer.Option("--minimal", help="Generate minimal config"),
    ] = False,
    full: Annotated[
        bool,
        typer.Option("--full", help="Generate config with all sections"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing config"),
    ] = False,
) -> None:
    """Initialize Quadkit in the current directory."""
    out = OutputManager()
    config_path = Path("application.yaml")

    if config_path.exists() and not force:
        out.error(
            f"{config_path} already exists",
            hint="Use --force to overwrite",
        )
        raise typer.Exit(1)

    project_name = Path.cwd().name
    template = _MINIMAL_CONFIG if minimal else _FULL_CONFIG if full else _MINIMAL_CONFIG
    content = template.format(project_name=project_name)
    config_path.write_text(content)
    out.success(f"Created {config_path}")


__all__ = ["app"]
