"""Project and module writers.

``render_project`` writes a whole application; ``render_module`` adds one
bounded context to an existing project in place.
"""

from __future__ import annotations

from pathlib import Path
import re

from quadkit.cli.scaffold.app_files import (
    _application_yaml,
    _infrastructure_py,
    _pyproject_toml,
)
from quadkit.cli.scaffold.metadata import (
    ProjectMetadataContext,
    render_project_metadata,
)
from quadkit.cli.scaffold.module_files import (
    _app_py,
    _component_files,
    _conftest,
    _controller_module,
    _module_controller,
    _module_scaffold_files,
    _modules_init,
    _package_line,
)
from quadkit.cli.scaffold.specs import ProjectTemplateSpec, resolve_template
from quadkit.cli.scaffold.support_files import (
    _env_example,
    _gitignore,
    _readme,
    _test_app,
)


def _sample_module_files(
    package_name: str,
    project_name: str,
) -> dict[str, str]:
    """The modular ``users`` sample bounded context (web templates)."""
    module = "users"
    files = _module_scaffold_files(package_name, module, "UsersModule")
    files[f"src/{package_name}/modules/{module}/controllers/__init__.py"] = (
        _package_line(f"{module}/controllers", ("controller",))
    )
    files[f"src/{package_name}/modules/{module}/controllers/root.py"] = (
        _module_controller(package_name, module)
    )
    return files


def _metadata_context(
    project_name: str,
    package_name: str,
    spec: ProjectTemplateSpec,
    files: dict[str, str],
) -> ProjectMetadataContext:
    """Build metadata from the same file map the scaffold will write."""
    layout: list[tuple[str, str]] = []
    descriptions = {
        "README.md": "human-facing project overview and quickstart",
        "application.yaml": "runtime configuration",
        "pyproject.toml": "dependencies, build metadata, and developer tools",
        ".env.example": "environment-variable examples; do not put real secrets here",
        "tests/": "project tests",
    }
    for path, description in descriptions.items():
        exists = (
            path in files
            if not path.endswith("/")
            else any(item.startswith(path) for item in files)
        )
        if exists:
            layout.append((path, description))

    package_root = f"src/{package_name}"
    if f"{package_root}/app.py" in files:
        layout.append((f"{package_root}/app.py", "composition root"))
    source_roots = sorted(
        {
            f"{package_root}/{path.split('/')[2]}/"
            for path in files
            if path.startswith(f"{package_root}/") and len(path.split("/")) > 3
        }
    )
    for path in source_roots:
        description = {
            "controllers": "HTTP controllers",
            "infrastructure": "application infrastructure adapters",
            "modules": "bounded contexts; add modules with `quadkit new module`",
            "shared": "cross-cutting application code",
        }.get(
            path.removeprefix(f"{package_root}/").rstrip("/"),
            "application package code",
        )
        layout.append((path, description))

    commands = [
        ('pip install -e ".[dev]"', "install the project and its test/lint tools"),
        ("python -m pytest", "run the project test suite"),
        ("python -m ruff check .", "lint the project"),
        (
            "quadkit gen list",
            "list available code generators (requires the QuadKit CLI)",
        ),
    ]
    if "web" in spec.features:
        commands.insert(
            1,
            ("quadkit dev", "run the development server (requires the QuadKit CLI)"),
        )

    return ProjectMetadataContext(
        project_name=project_name,
        package_name=package_name,
        summary=spec.description,
        template_name=spec.name,
        features=tuple(sorted(spec.features)),
        dependencies=tuple(spec.dependencies),
        layout=tuple(layout),
        commands=tuple(commands),
        notes=tuple(spec.notes),
    )


def _file_map(
    project_name: str,
    package_name: str,
    template: str,
) -> dict[str, str]:
    """Return the canonical file map for a project (path → content)."""
    spec = resolve_template(template)
    files = _component_files(package_name)
    files.update(
        {
            f"src/{package_name}/app.py": _app_py(project_name, package_name, spec),
            f"src/{package_name}/infrastructure/__init__.py": _infrastructure_py(
                package_name, spec
            ),
            f"src/{package_name}/modules/__init__.py": _modules_init(package_name, ()),
            "application.yaml": _application_yaml(project_name, spec),
            "pyproject.toml": _pyproject_toml(project_name, package_name, spec),
            "README.md": _readme(project_name, spec, package_name),
            ".env.example": _env_example(project_name),
            ".gitignore": _gitignore(),
            "tests/__init__.py": "",
            "tests/conftest.py": _conftest(project_name, package_name, spec),
            "tests/test_app.py": _test_app(spec),
        }
    )
    if "web" in spec.features:
        files[f"src/{package_name}/controllers/__init__.py"] = _package_line(
            "controllers", ("controller",)
        )
        files[f"src/{package_name}/controllers/api.py"] = _controller_module(
            project_name
        )
    files.update(
        render_project_metadata(
            _metadata_context(project_name, package_name, spec, files)
        )
    )
    return files


def render_project(
    template: str,
    project_name: str,
    target_dir: Path,
    *,
    force: bool = False,
) -> list[Path]:
    """Render a canonical Quadkit project into *target_dir*.

    Args:
        template: Template name (``api`` is the only template).
        project_name: Project / package name (dashes become underscores).
        target_dir: Destination directory (must be empty unless *force*).
        force: Allow writing into a non-empty directory.

    Returns:
        The list of created file paths.

    Raises:
        ValueError: Unknown template or non-empty target directory.
    """
    resolve_template(template)
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        raise ValueError(f"Directory {target_dir} is not empty")

    package_name = project_name.replace("-", "_")
    files = _file_map(project_name, package_name, template)

    created: list[Path] = []
    for relative, content in files.items():
        path = target_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            continue
        path.write_text(content)
        created.append(path)
    return created


_MODULE_IMPORT_RE = re.compile(
    r"^from (?P<pkg>[\w]+)\.modules\.(?P<slug>[\w-]+) import (?P<name>\w+Module)$",
    re.MULTILINE,
)


def _register_module_in_init(
    modules_init: Path,
    package_name: str,
    module: str,
    class_name: str,
) -> None:
    """Register *module* in the generated ``modules/__init__.py`` registry."""
    existing: dict[str, str] = {}
    for match in _MODULE_IMPORT_RE.finditer(modules_init.read_text()):
        if match.group("pkg") == package_name:
            existing[match.group("slug")] = match.group("name")
    existing[module] = class_name
    names = tuple(sorted(existing.items()))
    modules_init.write_text(_modules_init(package_name, names))


def render_module(module_name: str, target_dir: Path) -> list[Path]:
    """Create a bounded context inside a modular project.

    ``quadkit new module <name>`` writes
    ``src/<app>/modules/<name>/`` with a module boundary
    (``@module``), ``protocols.py``, ``provider.py`` and ``services.py`` and
    registers the module in ``modules/__init__.py`` so the composition root
    picks it up automatically.

    Args:
        module_name: Feature name (validated by the CLI).
        target_dir: Project root (must contain ``pyproject.toml``).

    Returns:
        The list of created file paths.

    Raises:
        ValueError: The module already exists.
    """
    from quadkit.cli.layout import read_project_layout

    layout = read_project_layout(target_dir)
    module_slug = module_name.replace("-", "_")
    module_dir = target_dir / "src" / layout.app_package / "modules" / module_slug
    if module_dir.exists() and any(module_dir.iterdir()):
        raise ValueError(f"Module {module_name!r} already exists in {module_dir}")

    class_name = (
        "".join(part.capitalize() for part in re.split(r"[-_]", module_name)) + "Module"
    )
    created: list[Path] = []
    for relative, content in _module_scaffold_files(
        layout.app_package, module_slug, class_name
    ).items():
        path = target_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(path)

    modules_init = module_dir.parent / "__init__.py"
    if modules_init.exists():
        _register_module_in_init(
            modules_init, layout.app_package, module_slug, class_name
        )
    return created
