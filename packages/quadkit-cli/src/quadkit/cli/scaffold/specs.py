"""Template catalogue and availability.

The specs table is what ``quadkit new project`` offers: each entry names the
provider packages it needs, so a template whose backend is absent from the
install is hidden rather than advertised.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quadkit.cli.layout import component_packages as _layout_component_packages
from quadkit.cli.layout import root_output_dirs as _layout_root_output_dirs
from quadkit.cli.package_names import packages_for, provider_available

TEMPLATE_ALIASES = {
    "fullstack": "full",
}


@dataclass(frozen=True)
class ProjectTemplateSpec:
    """Declarative description of a project template."""

    name: str
    description: str
    dependencies: tuple[str, ...]
    features: frozenset[str] = frozenset()
    notes: tuple[str, ...] = field(default_factory=tuple)


def _spec(
    name: str,
    description: str,
    dependencies: tuple[str, ...],
    features: frozenset[str] = frozenset(),
    notes: tuple[str, ...] = (),
) -> ProjectTemplateSpec:
    return ProjectTemplateSpec(name, description, dependencies, features, notes)


def _dependencies(*features: str, tools: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Build template dependencies from installed provider discovery."""

    return (*packages_for(*features), *tools)


_ALWAYS_AVAILABLE_FEATURES = frozenset({"web", "testing"})


def _missing_features(spec: ProjectTemplateSpec) -> tuple[str, ...]:
    """Return the features whose provider package is absent from this install."""

    return tuple(
        sorted(
            feature
            for feature in spec.features
            if feature not in _ALWAYS_AVAILABLE_FEATURES
            and not provider_available(feature)
        )
    )


def _template_is_available(spec: ProjectTemplateSpec) -> bool:
    """Hide templates whose optional providers are absent from this install."""

    return not _missing_features(spec)


_WEB_API_FEATURES = frozenset({"web", "sql"} if provider_available("sql") else {"web"})


_TEMPLATE_SPECS: dict[str, ProjectTemplateSpec] = {
    "minimal": _spec(
        "minimal",
        "Bare minimum Quadkit application",
        ("quadkit",),
    ),
    "api": _spec(
        "api",
        "REST API with the web framework",
        _dependencies("web", tools=("uvicorn",)),
        frozenset({"web"}),
    ),
    "web-api": _spec(
        "web-api",
        "REST API with optional persistence",
        _dependencies("web", "sql", tools=("uvicorn",)),
        _WEB_API_FEATURES,
        (
            (
                "Controllers are auto-discovered from src/<app>/controllers "
                "and from every module; run `quadkit gen controller users` "
                "(does not need a restart)."
            ),
        ),
    ),
    "graphql": _spec(
        "graphql",
        "GraphQL API with web + SQL + GraphQL",
        _dependencies("web", "sql", "graphql", tools=("uvicorn",)),
        frozenset({"web", "sql", "graphql"}),
        (
            (
                "Add serializers via `quadkit gen graphql product`; the schema "
                "package resolves through the project layout."
            ),
        ),
    ),
    "worker": _spec(
        "worker",
        "Background job processor",
        _dependencies("queue", "tasks", "sql"),
        frozenset({"queue", "tasks", "sql"}),
        (
            (
                "Define jobs with `quadkit gen task nightly_report`, then start "
                "a worker with your preferred queue backend."
            ),
        ),
    ),
    "full": _spec(
        "full",
        "Full application: auth, cache, storage, events, tasks, HTTP, monitoring, and SQL",
        _dependencies(
            "web",
            "sql",
            "auth",
            "cache",
            "storage",
            "events",
            "tasks",
            "http",
            "monitor",
            tools=("uvicorn",),
        ),
        frozenset({"web", "sql", "auth", "cache", "storage", "events", "tasks", "http", "monitor"}),
        (
            (
                "Auth ships with dev secret keys; replace QK_AUTH__SECRET_KEY "
                "and QK_AUTH__TOKEN__SECRET_KEY before deploying."
            ),
            (
                "Monitoring is not pre-wired: DatabaseModule and MonitorModule "
                "need an explicit import edge until the module graph allows it."
            ),
        ),
    ),
}


TEMPLATES: dict[str, ProjectTemplateSpec] = {
    name: spec for name, spec in _TEMPLATE_SPECS.items() if _template_is_available(spec)
}
if "full" in TEMPLATES:
    TEMPLATES["fullstack"] = TEMPLATES["full"]


def _available_aliases() -> dict[str, str]:
    """Return the aliases whose target template ships in this install."""

    return {
        alias: target
        for alias, target in TEMPLATE_ALIASES.items()
        if target in TEMPLATES
    }


def template_names() -> list[str]:
    """Return the available template names (aliases resolved)."""

    aliases = _available_aliases()
    return sorted(set(TEMPLATES) - set(TEMPLATE_ALIASES)) + sorted(aliases)


def resolve_template(name: str) -> ProjectTemplateSpec:
    """Resolve a template name (following aliases)."""

    target = TEMPLATE_ALIASES.get(name, name)
    spec = TEMPLATES.get(target)
    if spec is None:
        gated = _TEMPLATE_SPECS.get(target)
        missing = _missing_features(gated) if gated is not None else ()
        if missing:
            providers = ", ".join(missing)
            raise ValueError(
                f"Template {name!r} needs the {providers} provider package(s) "
                f"in this install. Available: {', '.join(template_names())}"
            )
        raise ValueError(
            f"Unknown template {name!r}. Available: {', '.join(template_names())}"
        )
    return spec


def component_packages() -> dict[str, tuple[str, ...]]:
    """Return the canonical structured component package map (copy)."""
    return _layout_component_packages()


def root_output_dirs() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return generator root output directories (copy)."""
    return _layout_root_output_dirs()
