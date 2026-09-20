"""Rendered project files: configuration, manifest and module imports.

Every function here returns the text of one file a scaffolded project boots
from: the typed ``application.yaml``, the ``pyproject.toml``, and the
composition root's imports and module registrations.
"""

from __future__ import annotations

from collections.abc import Sequence

from quadkit.cli.package_names import module_for
from quadkit.cli.scaffold.specs import ProjectTemplateSpec


def _application_yaml(project_name: str, spec: ProjectTemplateSpec) -> str:
    features = spec.features
    lines = [
        "# Quadkit configuration — validated by QuadkitConfig plus the",
        "# `quadkit.config` entry-point models (web/sql sections are typed).",
        "# Every top-level section is typed; unknown keys are reported at boot.",
        "",
        f"app_name: {project_name}",
        "debug: false",
        "env: development",
        "",
        "logging:",
        "  level: INFO",
        "  json_format: false",
        "",
        "modules: []",
        "discovery:",
        "  auto_discover: false          # modules are wired explicitly in app.py",
        "  entry_point_group: quadkit.modules",
        "",
        "health:",
        "  include_details: true",
        "",
    ]
    if "web" in features:
        lines += [
            "web:",
            "  server:",
            "    host: 127.0.0.1",
            "    port: 8000",
            "  api_docs:",
            "    # Serve the docs outside production; true publishes them in",
            "    # production as well.",
            "    enabled: null",
            "",
        ]
    if "sql" in features:
        lines += [
            "sql:",
            "  enabled: true",
            "  backend:",
            "    url: sqlite:///./dev.db",
            "  pool:",
            "    min_size: 1",
            "    max_size: 5",
            "",
        ]
    if "auth" in features:
        lines += [
            "auth:",
            "  enabled: true",
            "  # Development keys — JWTConfig and AuthConfig both require one.",
            "  # Override with QK_AUTH__SECRET_KEY / QK_AUTH__TOKEN__SECRET_KEY.",
            f'  secret_key: "{project_name}-dev-auth-0123456789abcdef"',
            "  token:",
            f'    secret_key: "{project_name}-dev-token-0123456789abcdef"',
            "    algorithm: HS256",
            "",
        ]
    if "features" in features:
        lines += [
            "features:",
            "  enabled: true",
            "  default_enabled: true",
            "  cache_ttl: 60",
            "",
        ]
    if "cache" in features:
        lines += [
            "cache:",
            "  enabled: true",
            "  # backend defaults to an in-process memory store; add Redis via",
            "  # `backends` when you move to multi-worker deployments.",
            "",
        ]
    if "tasks" in features:
        lines += [
            "tasks:",
            "  enabled: true",
            "  # worker.backend defaults to the in-process scheduler in development.",
            "",
        ]
    if "queue" in features:
        lines += [
            "queue:",
            "  enabled: true",
            "  # In development the queue runs in-process; configure a broker",
            "  # (Redis, RabbitMQ, SQS) before scaling out.",
            "",
        ]
    if "monitor" in features:
        lines += [
            "monitor:",
            "  enabled: true",
            "  # OpenTelemetry/prometheus exporters are opt-in via env.",
            "",
        ]
    if "graphql" in features:
        lines += [
            "graphql:",
            "  enabled: true",
            "  path: /graphql",
            "  playground: true",
            "",
        ]
    return "\n".join(lines)


def _pyproject_toml(
    project_name: str,
    package_name: str,
    spec: ProjectTemplateSpec,
) -> str:
    deps = "".join(f'    "{dep}",\n' for dep in spec.dependencies)
    wheel = f'    "src/{package_name}",\n'
    return f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "{spec.description}"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
{deps}]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "ruff>=0.6.0",
    "mypy>=1.10.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = [
{wheel}]

[tool.quadkit]
module = "{package_name}.app:app"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 88
target-version = "py311"
"""


def _module_imports(features: frozenset[str]) -> list[str]:
    """Alphabetical import lines for the feature modules."""
    names: list[str] = []
    if "web" in features:
        names.append(f"from {module_for('web')} import WebModule")
    if "sql" in features:
        names.append(f"from {module_for('sql')} import DatabaseModule")
    if "graphql" in features:
        names.append(f"from {module_for('graphql')} import GraphQLModule")
    if "auth" in features:
        names.append(f"from {module_for('auth')} import AuthModule")
    if "admin" in features:
        names.append(f"from {module_for('admin')} import AdminModule")
        names.append(
            f"from {module_for('admin', 'config')} import AdminAuthConfig, "
            "AdminConfig, AdminSecurityConfig"
        )
    if "cache" in features:
        names.append(f"from {module_for('cache')} import CacheModule")
    if "features" in features:
        names.append(f"from {module_for('features')} import FeatureFlagsModule")
    if "tasks" in features:
        names.append(f"from {module_for('tasks')} import TasksModule")
    if "queue" in features:
        names.append(f"from {module_for('queue')} import QueueModule")
    if "monitor" in features:
        names.append(f"from {module_for('monitor')} import MonitorModule")
    names.sort()
    return names


def _feature_calls(
    features: frozenset[str],
    project_name: str,
    *,
    web_discover: Sequence[str] | None,
    include_graphql: bool = True,
) -> list[tuple[str, list[str]]]:
    """Ordered ``(comment, configure-call lines)`` pairs for the features.

    The web module is appended last so the server boots after every
    dependency is registered.  ``web_discover`` lists the packages
    ``WebModule`` scans for controllers -- the app-root ``controllers``
    package and ``modules`` -- and when ``None`` the web call is omitted.  ``include_graphql=False`` skips the GraphQL call (used
    by the modular infrastructure layer, where the surface is wired by the
    composition root next to the web module).
    """
    calls: list[tuple[str, list[str]]] = []
    if "sql" in features:
        calls.append(
            (
                "# Persistence - reads the `sql:` section of application.yaml.",
                ["DatabaseModule.configure()"],
            )
        )
    if "auth" in features:
        calls.append(
            (
                "# Authentication - reads the `auth:` section.",
                ["AuthModule.configure()"],
            )
        )
    if "features" in features:
        calls.append(
            (
                "# Feature flags - read by the admin panel.",
                ["FeatureFlagsModule.configure()"],
            )
        )
    if "cache" in features:
        calls.append(
            (
                "# Caching - reads the `cache:` section.",
                ["CacheModule.configure()"],
            )
        )
    if "admin" in features:
        calls.append(
            (
                "# Admin dashboard - dev config skips the setup token.",
                [
                    "AdminModule.configure(",
                    "    config=AdminConfig(",
                    "        auth=AdminAuthConfig(",
                    "            security=AdminSecurityConfig(",
                    "                setup_token_optin_unsafe=True,",
                    "            ),",
                    "        ),",
                    "    ),",
                    "),",
                ],
            )
        )
    if "tasks" in features:
        calls.append(
            (
                "# Background tasks - reads the `tasks:` section.",
                ["TasksModule.configure()"],
            )
        )
    if "queue" in features:
        calls.append(
            (
                "# Message queue - reads the `queue:` section.",
                ["QueueModule.configure()"],
            )
        )
    if "monitor" in features:
        calls.append(
            (
                "# Metrics/tracing - reads the `monitor:` section.",
                ["MonitorModule.configure()"],
            )
        )
    if "graphql" in features and include_graphql:
        calls.append(
            (
                "# GraphQL - reads the `graphql:` section.",
                ["GraphQLModule.configure()"],
            )
        )
    if "web" in features and web_discover is not None:
        calls.append(
            (
                "# Web server - controllers written by `quadkit gen controller` are",
                _web_configure_lines(web_discover),
            )
        )
    return calls


def _web_configure_lines(web_discover: Sequence[str]) -> list[str]:
    """``WebModule.configure(...)``, wrapped when one line will not fit.

    The call is rendered at twelve spaces of indentation inside
    ``add_modules([...])``, and a package name is a project name, so a
    single-line form is a formatting bug waiting for a long-ish project.
    Line length is checked rather than guessed: scaffolded projects are
    linted by their own ruff config, and E501 there reads as the framework
    shipping broken code.
    """
    roots = [f'"{root}"' for root in web_discover]
    single = f"WebModule.configure(discover=[{', '.join(roots)}])"
    # +12 indent, +1 for the trailing comma _render_calls appends.
    if 12 + len(single) + 1 <= 88:
        return [single]
    return [
        "WebModule.configure(",
        "    discover=[",
        *[f"        {root}," for root in roots],
        "    ]",
        ")",
    ]


def _render_calls(calls: list[tuple[str, list[str]]], indent: int) -> list[str]:
    """Render ``(comment, lines)`` pairs at *indent* spaces."""
    rendered: list[str] = []
    for comment, call_lines in calls:
        rendered.append(f"{' ' * indent}# {comment.lstrip('#').strip()}")
        for index, line in enumerate(call_lines):
            if index == len(call_lines) - 1 and not line.rstrip().endswith(","):
                line = f"{line},"
            rendered.append(f"{' ' * indent}{line}")
    return rendered


def _render_infra_calls(calls: list[tuple[str, list[str]]]) -> list[str]:
    """Render feature calls as ``modules.append(...)`` statements."""
    rendered: list[str] = []
    for comment, call_lines in calls:
        rendered.append(f"    # {comment.lstrip('#').strip()}")
        rendered.append("    modules.append(")
        for line in call_lines:
            rendered.append(f"        {line}")
        rendered.append("    )")
    return rendered


def _infrastructure_py(package_name: str, spec: ProjectTemplateSpec) -> str:
    """Modular shared infrastructure layer (db, cache, events, monitoring)."""
    # web + graphql are application surfaces and are wired by the
    # composition root next to the module registry, never here.
    features = spec.features - {"web", "graphql"}
    imports = _module_imports(features)
    imports.append("from quadkit.di.module import DynamicModule")
    imports.sort()
    calls = _feature_calls(features, package_name, web_discover=None)
    body = _render_infra_calls(calls)
    return f'''"""Shared infrastructure wiring for {package_name}.

Feature modules configured here (persistence, auth, cache, tasks, queue,
monitoring) are registered before the web surface and the bounded contexts
in ``src/{package_name}/modules/``.  Replace or extend entries here when you
swap backends.
"""

from __future__ import annotations

{chr(10).join(imports)}


def infrastructure_modules() -> list[DynamicModule]:
    """Return the configured infrastructure modules for this application."""
    modules: list[DynamicModule] = []
{chr(10).join(body)}
    return modules
'''
