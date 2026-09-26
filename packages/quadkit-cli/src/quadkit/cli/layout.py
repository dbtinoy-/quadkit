"""Canonical generator -> project-path map.

Single source of truth shared by:

- ``quadkit new project`` scaffolding (which component packages exist)
- ``quadkit gen`` (where a generator writes inside the current project)
- the alignment gate (``dev/checks/generator_output.py``)

**A project has no structure.** There is one tree, and a node either belongs
to a module or it does not::

    src/<app>/main.py                      composition root
    src/<app>/controllers/...              feature code, unscoped
    src/<app>/shared/middleware/...        cross-cutting, decided by the kind
    src/<app>/modules/sales/controllers/   feature code scoped to a module

Two questions decide every path, each asked of exactly one authority: *is
this component cross-cutting?* (``ComponentDir.shared``) and *is this node in
a module?* (the caller's ``module`` argument). The project-wide
``minimal``/``structured``/``modular`` mode that used to sit on top of them
was a second, coarser answer to the same question, and it made growth a
migration: adopting bounded contexts relocated every file in the project.
Now scoping a node moves that node.

See ``docs/PROJECT_LAYOUT.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

#: Package holding cross-cutting components inside the app package.
SHARED_DIR = "shared"
#: Package holding bounded contexts inside the app package.
MODULES_DIR = "modules"


@dataclass(frozen=True)
class ComponentDir:
    """One component package and the generators that write into it.

    Attributes:
        structured: Path under ``src/`` in the structured layout (equals the
            generator contributors' ``default_output_dir`` suffix).
        modular: Same suffix used under ``modules/<feature>/`` or ``shared/``.
        shared: True when the component is cross-cutting (lives in the
            modular ``shared/`` layer instead of inside one feature module).
        generators: Generator names that emit into this package.
    """

    structured: str
    modular: str
    shared: bool
    generators: tuple[str, ...]


# The canonical map.  Keys mirror ``quadkit gen`` defaults exactly.
COMPONENTS: tuple[ComponentDir, ...] = (
    ComponentDir("admin/actions", "admin/actions", False, ("admin_action",)),
    ComponentDir("admin/resources", "admin/resources", False, ("admin_resource",)),
    ComponentDir("audit", "audit", True, ("audited",)),
    # ``auth``, ``contracts`` and ``validators`` carry no generators on
    # purpose: no registered generator writes there yet (the CLI ships
    # ``provider`` and ``test``; subsystems contribute the rest), and a
    # ``generators`` entry is the map's authorisation for a generator's
    # declared output directory, so it should name a generator that exists.
    # The rows are the map's answer for *placement and scope*, which is what
    # the builder needed to delete its own copy of them
    # (docs/upstream/2026-09-02-component-rows.md).
    # API-key issuance and verification. Cross-cutting by definition: one
    # key store, checked by every bounded context.
    ComponentDir("auth", "auth", True, ()),
    ComponentDir("clients", "clients", False, ("api_client",)),
    ComponentDir("commands", "commands", False, ("command",)),
    ComponentDir("consumers", "consumers", False, ("message_consumer",)),
    # Request/response schemas shared across controllers. They are the
    # interface between a context and its callers, so they cannot be
    # module-local without every consumer reaching across a boundary.
    ComponentDir("contracts", "contracts", True, ()),
    ComponentDir("controllers", "controllers", False, ("controller",)),
    # Cross-cutting DI providers. Every quadkit subsystem keeps its own
    # provider at ``<subsystem>/di/provider.py`` (30 of them, no
    # exceptions), so a generated provider reads like the framework it
    # is built on. The ``providers`` row below is kept for projects
    # that already generated into it.
    ComponentDir("di", "di", True, ("provider",)),
    ComponentDir("domains", "domains", False, ("domain",)),
    ComponentDir("errors", "errors", True, ("error",)),
    ComponentDir("events", "events", False, ("event",)),
    ComponentDir("features", "features", True, ("feature_flag",)),
    ComponentDir("filters", "filters", True, ("exception_filter", "filter")),
    # Cross-cutting, like ``filters`` above: ``@require_auth()`` decorates
    # controllers in every bounded context, and the palette already scopes
    # ``auth``/``role`` as shared kinds. While this row said module-local,
    # the two answers met at generation time and a modular app containing
    # an Auth Guard could not be generated at all (playground TASK-6 /
    # MODULAR-3).
    ComponentDir("guards", "guards", True, ("auth_guard", "guard")),
    ComponentDir("handlers", "handlers", False, ("event_handler",)),
    ComponentDir("health", "health", True, ("health",)),
    ComponentDir("interceptors", "interceptors", True, ("interceptor",)),
    ComponentDir("mcp", "mcp", True, ("mcp-controller",)),
    ComponentDir("metrics", "metrics", True, ("metric",)),
    ComponentDir("middleware", "middleware", True, ("middleware",)),
    ComponentDir("notifications", "notifications", False, ("notification_template",)),
    ComponentDir("pipelines", "pipelines", False, ("pipeline",)),
    ComponentDir("policies", "policies", False, ("auth_policy",)),
    ComponentDir("projections", "projections", False, ("projection",)),
    # Superseded by the ``di`` row above; kept (with no generators) so a
    # project that already has ``shared/providers/`` keeps resolving.
    ComponentDir("providers", "providers", True, ()),
    ComponentDir("queries", "queries", False, ("query",)),
    ComponentDir(
        "repositories",
        "repositories",
        False,
        ("cache_repo", "document_repo", "repository"),
    ),
    ComponentDir("sagas", "sagas", False, ("saga", "saga_step")),
    ComponentDir("schema", "schema", True, ("graphql",)),
    ComponentDir("schema/dataloaders", "schema/dataloaders", True, ("dataloader",)),
    ComponentDir("search", "search", True, ("search_index",)),
    # Generated seeders live inside the application package so they are
    # importable: a project boots them from its persistence provider, and
    # `quadkit db seed` imports the same modules. ``seeds`` (project root)
    # stays resolvable in ROOT_DIRS below, because that is where every
    # project generated before 2026-09-23 kept them and where the command
    # still looks second.
    ComponentDir("seeders", "seeders", True, ("seeder",)),
    ComponentDir("services", "services", False, ("service",)),
    ComponentDir("storage/backends", "storage/backends", True, ("storage_driver",)),
    ComponentDir("tasks", "tasks", False, ("task",)),
    ComponentDir("tenancy", "tenancy", True, ("tenant_resolver",)),
    # Per-entity rules. They know an entity's fields, so they belong
    # wherever that entity belongs: module-local.
    ComponentDir("validators", "validators", False, ()),
    ComponentDir(
        "vector/collections", "vector/collections", True, ("vector_collection",)
    ),
    ComponentDir("webhooks", "webhooks", False, ("webhook",)),
    ComponentDir("websocket", "websocket", False, ("websocket",)),
    ComponentDir("workflows", "workflows", False, ("workflow_def",)),
)

# Root-level output directories of the generator SDK (no ``src/`` prefix).
ROOT_DIRS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("migrations/versions", ("migration",)),
    # ``seeds`` is legacy-but-supported: the ``seeders`` component above is
    # where the generator writes now, while this row keeps ``quadkit gen
    # seeder --output seeds`` and projects generated before 2026-09-23
    # resolvable. ``quadkit db seed`` looks here second.
    ("seeds", ("seeder",)),
    ("tests/unit", ("test",)),
)

# Generators that emit a single module at the project ``src`` root.
SRC_ROOT_GENERATORS: frozenset[str] = frozenset({"mcp-server"})

# ``resource`` declares ``src`` but writes into ``<dir>/controllers`` (it
# delegates to the controller generator), so it is module-local everywhere.
_RESOURCE_OUTPUT = "resource"

_COMPONENTS_BY_PATH: dict[str, ComponentDir] = {
    component.structured: component for component in COMPONENTS
}
_COMPONENTS_BY_GENERATOR: dict[str, ComponentDir] = {
    generator: component
    for component in COMPONENTS
    for generator in component.generators
}
_ROOTS_BY_PATH: dict[str, tuple[str, ...]] = dict(ROOT_DIRS)
_ROOTS_BY_GENERATOR: dict[str, str] = {
    generator: path for path, generators in ROOT_DIRS for generator in generators
}


@dataclass(frozen=True)
class ProjectLayout:
    """Project layout metadata read from ``[tool.quadkit]``.

    Only the application package is recorded. There is nothing else to
    record: the tree is the same for every project, and where a component
    lands is decided per node rather than per project.
    """

    app_package: str = "app"
    declared: bool = False

    def module_target(self) -> str:
        """Return the default ``[tool.quadkit] module`` target.

        ``app.py`` is the composition root: it defines ``create_app`` and
        exposes the ``app`` it returns. ``main.py`` only imports that, so
        booting it is a level of indirection with nothing behind it.
        """
        return f"{self.app_package}.app:app"


def read_project_layout(cwd: Path | None = None) -> ProjectLayout:
    """Read ``[tool.quadkit]`` from ``pyproject.toml`` in *cwd*.

    ``app_package`` is derived from ``module`` (``"my_app.main:app"`` ->
    ``"my_app"``); ``declared`` is False when there is no project metadata
    to read.
    """
    root = Path(cwd or Path.cwd())
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return ProjectLayout()
    try:
        data = tomllib.loads(pyproject.read_text())
    except Exception:  # noqa: BLE001 — a bad layout file falls back to the default layout
        return ProjectLayout()
    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        return ProjectLayout()
    quadkit_tool = tool.get("quadkit", {})
    if not isinstance(quadkit_tool, dict):
        return ProjectLayout()

    module_target = quadkit_tool.get("module", "")
    app_package = "app"
    if isinstance(module_target, str) and module_target.strip():
        raw_package = module_target.split(":")[0].split(".")[0]
        if raw_package:
            app_package = raw_package

    return ProjectLayout(app_package=app_package, declared=bool(quadkit_tool))


def component_metadata(output_dir: str) -> ComponentDir | None:
    """Return the component metadata for a ``src/``-relative output dir.

    ``"src"`` and root directories return ``None``; callers should treat the
    ``src``-root case through :data:`SRC_ROOT_GENERATORS`.
    """
    return _COMPONENTS_BY_PATH.get(_strip_src(output_dir) or "")


def generator_component(generator: str) -> ComponentDir | None:
    """Return the component a generator writes into, or ``None``."""
    return _COMPONENTS_BY_GENERATOR.get(generator)


def generator_root_output(generator: str) -> str | None:
    """Return the root output path (``migrations/versions`` etc.) or None."""
    return _ROOTS_BY_GENERATOR.get(generator)


def resolve_output_dir(
    default_output_dir: str,
    *,
    app_package: str = "app",
    module: str | None = None,
    generator: str | None = None,
) -> str:
    """Map a generator's default output dir onto the project tree.

    One algorithm, no modes::

        "src"                          -> src/<app>                (composition root)
        "src/<component>", shared      -> src/<app>/shared/<component>
        "src/<component>", no module   -> src/<app>/<component>
        "src/<component>", module      -> src/<app>/modules/<module>/<component>
        "tests/unit" with a module     -> src/<app>/modules/<module>/tests
        other root dirs                -> unchanged

    Unscoped feature code lands at the app root rather than in ``shared/``.
    That is the whole reason a project can start without bounded contexts and
    grow into them: ``shared/`` keeps meaning *cross-cutting*, so nothing has
    to be moved out of it later, and a node that joins a module moves alone.

    Args:
        default_output_dir: The contributor-declared default (``src/...``,
            ``migrations/versions``, ``seeds``, ``tests/unit`` or ``src``).
        app_package: The application package (``my_app``).
        module: Bounded context this node belongs to, if any.
        generator: Optional generator name — needed for the ``src``-root
            generators whose real target differs from their declared default
            (``resource`` writes into ``<dir>/controllers``).

    Returns:
        The project-relative output path.

    Raises:
        ValueError: Unknown output directory.
    """
    if default_output_dir == "src":
        if generator == _RESOURCE_OUTPUT and module is not None:
            # Delegates to the controller generator: <dir>/controllers.
            return f"src/{app_package}/{MODULES_DIR}/{module}"
        if module is not None:
            return f"src/{app_package}/{MODULES_DIR}/{module}"
        return f"src/{app_package}"

    if _looks_like_src(default_output_dir):
        suffix = _strip_src(default_output_dir)
        if not suffix:
            return f"src/{app_package}"
        component = _COMPONENTS_BY_PATH.get(suffix)
        if component is not None and component.shared:
            # Cross-cutting by kind: never inside one bounded context, and
            # never at the app root either -- shared/ is where "belongs to
            # everything" lives, and it says so in the path.
            return f"src/{app_package}/{SHARED_DIR}/{suffix}"
        if module is None:
            return f"src/{app_package}/{suffix}"
        return f"src/{app_package}/{MODULES_DIR}/{module}/{suffix}"

    if default_output_dir in _ROOTS_BY_PATH:
        if default_output_dir == "tests/unit" and module is not None:
            return f"src/{app_package}/{MODULES_DIR}/{module}/tests"
        return default_output_dir

    raise ValueError(f"Unknown generator output directory: {default_output_dir}")


def validate_definition(name: str, default_output_dir: str) -> str | None:
    """Return an error message when a generator definition drifts from the map.

    Returns ``None`` when *name*/*default_output_dir* are aligned with the
    canonical layout (component packages, root dirs, or the two ``src``-root
    generators).
    """
    if default_output_dir == "src":
        if name not in SRC_ROOT_GENERATORS and name != _RESOURCE_OUTPUT:
            return (
                f"{name!r} writes to the package root 'src' but is not a "
                "declared src-root generator"
            )
        if name == _RESOURCE_OUTPUT:
            # The resource generator delegates to controllers; accept both
            # its declared 'src' default and the concrete component path.
            return None
        return None

    component = _COMPONENTS_BY_PATH.get(_strip_src(default_output_dir) or "")
    if component is not None:
        if name not in component.generators:
            return (
                f"{name!r} writes to 'src/{component.structured}' but that "
                f"package is owned by {', '.join(component.generators)}"
            )
        return None

    root_generators = _ROOTS_BY_PATH.get(default_output_dir)
    if root_generators is None:
        return f"{name!r} writes to unknown directory {default_output_dir!r}"
    if name not in root_generators:
        return (
            f"{name!r} writes to '{default_output_dir}' but that directory "
            f"is owned by {', '.join(root_generators)}"
        )
    return None


def component_packages() -> dict[str, tuple[str, ...]]:
    """Return ``{structured path: generators}`` for scaffolding (copy)."""
    return {component.structured: component.generators for component in COMPONENTS}


def root_output_dirs() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return the root generator output directories (copy)."""
    return ROOT_DIRS


def _looks_like_src(output_dir: str) -> bool:
    return output_dir == "src" or output_dir.startswith("src/")


def _strip_src(output_dir: str) -> str:
    if output_dir == "src":
        return ""
    if output_dir.startswith("src/"):
        return output_dir[len("src/") :]
    return output_dir


__all__ = [
    "COMPONENTS",
    "MODULES_DIR",
    "ROOT_DIRS",
    "SHARED_DIR",
    "SRC_ROOT_GENERATORS",
    "ComponentDir",
    "ProjectLayout",
    "component_metadata",
    "component_packages",
    "generator_component",
    "generator_root_output",
    "read_project_layout",
    "resolve_output_dir",
    "root_output_dirs",
    "validate_definition",
]
