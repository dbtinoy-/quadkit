"""The project template catalogue.

``quadkit new project`` ships one canonical starter -- ``api``. Variation is
additive, not template-driven: richer applications are grown from the same
scaffold with ``quadkit add`` and ``quadkit gen`` rather than chosen from a
lineup at scaffold time, so nothing here gates on installed providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quadkit.cli.layout import component_packages as _layout_component_packages
from quadkit.cli.layout import root_output_dirs as _layout_root_output_dirs
from quadkit.cli.package_names import packages_for


@dataclass(frozen=True)
class ProjectTemplateSpec:
    """Declarative description of a project template."""

    name: str
    description: str
    dependencies: tuple[str, ...]
    features: frozenset[str] = frozenset()
    notes: tuple[str, ...] = field(default_factory=tuple)
    # App-root providers as ``(module, class_name)`` pairs, e.g.
    # ``("my_api.shared.di.handlers_provider",
    # "HandlersRegistrationProvider")``. Fresh ``quadkit new`` projects pass
    # none; the playground passes one per emitted registration provider so
    # the composition root wires what the scaffold generated.
    providers: tuple[tuple[str, str], ...] = ()


def _spec(
    name: str,
    description: str,
    dependencies: tuple[str, ...],
    features: frozenset[str] = frozenset(),
    notes: tuple[str, ...] = (),
    providers: tuple[tuple[str, str], ...] = (),
) -> ProjectTemplateSpec:
    return ProjectTemplateSpec(
        name, description, dependencies, features, notes, providers
    )


def _dependencies(*features: str, tools: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Build template dependencies from installed provider discovery."""

    return (*packages_for(*features), *tools)


_TEMPLATE_SPECS: dict[str, ProjectTemplateSpec] = {
    "api": _spec(
        "api",
        "REST API with the web framework",
        _dependencies("web", tools=("uvicorn",)),
        frozenset({"web"}),
    ),
}


TEMPLATES: dict[str, ProjectTemplateSpec] = dict(_TEMPLATE_SPECS)


def template_names() -> list[str]:
    """Return the available template names (`api` is the only template)."""

    return sorted(TEMPLATES)


def resolve_template(name: str) -> ProjectTemplateSpec:
    """Resolve a template name to its spec."""
    spec = TEMPLATES.get(name)
    if spec is None:
        raise ValueError(
            f"Unknown template {name!r}. The only available template is 'api'."
        )
    return spec


def component_packages() -> dict[str, tuple[str, ...]]:
    """Return the canonical structured component package map (copy)."""
    return _layout_component_packages()


def root_output_dirs() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return generator root output directories (copy)."""
    return _layout_root_output_dirs()
