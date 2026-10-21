"""Rendered tests, README, environment template and gitignore."""

from __future__ import annotations

from quadkit.cli.scaffold.specs import ProjectTemplateSpec


def _test_app(spec: ProjectTemplateSpec) -> str:
    web_bootable = "web" in spec.features
    if web_bootable:
        return '''"""Smoke tests for the scaffolded application."""
from __future__ import annotations

import httpx


async def test_root(app) -> None:
    """GET / returns 200 with the service banner."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_readiness_probe(app) -> None:
    """The framework readiness probe is served and healthy."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
'''
    return '''"""Smoke tests for the scaffolded application."""
from __future__ import annotations

from quadkit.app import Application


async def test_boots(application: Application) -> None:
    """The application reaches the RUNNING state."""
    assert application.is_running
'''


def _readme(
    project_name: str,
    spec: ProjectTemplateSpec,
    package_name: str,
) -> str:
    features = spec.features
    run = "quadkit dev" if "web" in features else "pytest"
    gen_example = (
        "quadkit gen controller users"
        if "web" in features
        else "quadkit gen task nightly_report"
    )
    sections = ["```bash", f"cd {project_name}", "pip install -e .", f"{run}", "```"]
    if "web" in features:
        sections.append("")
        sections.append("`/` and `/health` are served by the scaffolded controllers.")
    sections += [
        "",
        "## Generators",
        "",
        "The bootstrap is aligned with the canonical generator layout:",
        "",
        "```bash",
        f"{gen_example}",
        "```",
        "",
        "List all generators with `quadkit gen list`.",
        "",
        "## Project layout",
        "",
        "- `application.yaml` — typed configuration (see `quadkit config show`)",
        f"- `src/{package_name}/app.py` — composition root (`create_app`)",
        (
            f"- `src/{package_name}/controllers/`, `src/{package_name}/services/`, "
            "… — feature components (created on demand)"
        ),
        f"- `src/{package_name}/shared/` — cross-cutting packages",
        (
            f"- `src/{package_name}/modules/` — bounded contexts "
            "(`quadkit new module <name>`)"
        ),
        "- `tests/` — boot smoke tests (pytest, asyncio-mode auto)",
        "",
    ]
    return "\n".join(
        [f"# {project_name}\n", f"{spec.description}.\n", "## Quickstart\n", *sections]
    )


def _env_example(project_name: str) -> str:
    # One commented line per key application.yaml ships (the mirror rule):
    # uncomment only where a deployment overrides the file's default.
    return f"""# Quadkit environment overrides (QK_<SECTION>__<FIELD> syntax).
# Each line mirrors a key application.yaml ships with the same value —
# copy to .env and uncomment what you need; leave the rest commented.

# QK_APP_NAME={project_name}
# QK_DEBUG=false
# QK_ENV=development

# Web server (web.server.host / web.server.port)
# QK_WEB__SERVER__HOST=127.0.0.1
# QK_WEB__SERVER__PORT=8000

# Datasource (sql.backend.url / sql.pool)
# QK_SQL__BACKEND__URL=sqlite:///./dev.db
# QK_SQL__POOL__MIN_SIZE=1
# QK_SQL__POOL__MAX_SIZE=5

# Auth secrets (auth.secret_key / auth.token.secret_key) — the yaml ships
# development placeholders; set real values before deploying
# QK_AUTH__SECRET_KEY=change-me-in-production
# QK_AUTH__TOKEN__SECRET_KEY=change-me-in-production

# Logging (logging.level / logging.json_format)
# QK_LOGGING__LEVEL=INFO
# QK_LOGGING__JSON_FORMAT=false

# Health endpoint (health.include_details)
# QK_HEALTH__INCLUDE_DETAILS=true
"""


def _gitignore() -> str:
    return """# Python
__pycache__/
*.py[cod]
.venv/
venv/
dist/
build/
*.egg-info/

# Local environments
.env
.env.local

# Databases / caches / logs
*.db
*.sqlite3
*.log
coverage/
.pytest_cache/
.mypy_cache/
.ruff_cache/
"""
