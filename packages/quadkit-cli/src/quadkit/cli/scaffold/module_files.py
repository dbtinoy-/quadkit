"""Rendered application and module files.

The composition root (``app.py``), the module boundary ``quadkit new module``
creates, and the component packages a fresh project pre-creates.
"""

from __future__ import annotations

import textwrap

from quadkit.cli.layout import COMPONENTS, ROOT_DIRS
from quadkit.cli.package_names import module_for
from quadkit.cli.scaffold.app_files import (
    _web_configure_lines,
)
from quadkit.cli.scaffold.specs import ProjectTemplateSpec


def _package_line(package: str, generators: tuple[str, ...]) -> str:
    """Docstring for a pre-created package.

    A shared row can exist with no generator behind it (``contracts``,
    ``auth``): the map answers *where* the package lives, and the code that
    fills it is written by hand or by a tool outside the CLI. Saying
    "Writers:  (quadkit gen)" in that case would advertise a command that
    does not exist.
    """
    names = ", ".join(generators)
    if not names:
        return f'"""{package} package."""\n'
    return f'"""{package} package.\n\nWriters: {names} (quadkit gen)."""\n'


def _component_files(package_name: str) -> dict[str, str]:
    """Pre-created ``__init__.py`` files for a fresh project.

    Only the packages whose location can never change are created up front:
    the cross-cutting ``shared/`` components and the root output dirs. Feature
    components are left to the generators, because where they land is a fact
    about the node being generated (app root until it joins a module), not a
    fact about the project.
    """
    files: dict[str, str] = {}
    for component in COMPONENTS:
        # A shared row with no generator behind it is a *resolution* row, not
        # a package the scaffold creates: `providers` exists so a project
        # generated into it before the `di` row landed keeps resolving, and
        # `auth`/`contracts` exist because the map is where a project's
        # cross-cutting packages are declared -- nothing in the CLI writes
        # there, so pre-creating them would put an unexplained empty package
        # in every fresh project and change the scaffold for existing users.
        if component.shared and component.generators:
            path = f"src/{package_name}/shared/{component.modular}"
            files[f"{path}/__init__.py"] = _package_line(
                f"{component.modular} (shared)", component.generators
            )
    for package, generators in ROOT_DIRS:
        files[f"{package}/__init__.py"] = _package_line(package, generators)
    files[f"src/{package_name}/__init__.py"] = f'"""{package_name} package."""\n'
    files[f"src/{package_name}/py.typed"] = ""
    return files


def _modules_init(package_name: str, names: tuple[tuple[str, str], ...]) -> str:
    """Modular ``modules/__init__.py`` with the module registry."""
    imports = "\n".join(
        f"from {package_name}.modules.{slug} import {name}" for slug, name in names
    )
    entries = "".join(f"    {name},\n" for _slug, name in names)
    header = f"from __future__ import annotations\n\n{imports}\n\n" if imports else ""
    return f'''"""Application feature modules.

``quadkit new module <name>`` appends bounded contexts here; the composition
root registers every entry in ``MODULES``.  ``quadkit gen <component> <name>
--module <feature>`` writes module-local components into the matching module
package.
"""

{header}MODULES: list[type] = [
{entries}]
'''


def _module_boundary(
    module: str,
    class_name: str,
    title: str,
) -> str:
    """A modular feature-module boundary (``quadkit new module`` output)."""
    return f'''"""{module} module - bounded context.

``quadkit gen <component> <name> --module {module}`` writes module-local
components (controllers, domains, services, repositories, ...) into this
package; ``quadkit gen`` without ``--module`` writes cross-cutting
components into the shared layer.
"""

from __future__ import annotations

from quadkit.di.module import Module, module


@module()
class {class_name}(Module):
    """{title} module."""
'''


def _module_protocols(module: str, title: str) -> str:
    """Public contract file for a feature module."""
    return f'''"""Public contracts for the {module} module.

Other modules import from here only — never from implementations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class {title.replace(" ", "")}ServiceProtocol(Protocol):
    """Contract exposed by the {module} module."""
'''


def _module_provider(module: str, title: str) -> str:
    """DI provider file for a feature module."""
    return f'''"""DI provider for the {module} module."""

from __future__ import annotations

from quadkit.di.provider import Provider


class {title.replace(" ", "")}Provider(Provider):
    """Registers and boots {module} services."""
'''


def _module_scaffold_files(
    package_name: str, module: str, class_name: str
) -> dict[str, str]:
    """Bare files for ``quadkit new module <name>``."""
    title = class_name.removesuffix("Module").replace("_", " ").title()
    files: dict[str, str] = {
        f"src/{package_name}/modules/{module}/__init__.py": _module_boundary(
            module, class_name, title
        ),
        f"src/{package_name}/modules/{module}/protocols.py": _module_protocols(
            module, title
        ),
        f"src/{package_name}/modules/{module}/provider.py": _module_provider(
            module, title
        ),
        f"src/{package_name}/modules/{module}/services.py": (
            f'"""Application services for the {module} module."""\n'
        ),
    }
    return files


def _app_py(
    project_name: str,
    package_name: str,
    spec: ProjectTemplateSpec,
) -> str:
    """Render the composition root.

    One root serves a flat project and one full of bounded contexts. It
    registers the shared ``infrastructure_modules()`` layer, then
    ``MODULES`` -- empty until ``quadkit new module`` appends to it -- and
    points web discovery at *both* the app-root ``controllers`` package and
    ``modules``. Adding the first module therefore changes one file,
    ``modules/__init__.py``, and never this one.

    This is also the file the builder emits for a canvas-built project, via
    :func:`quadkit.builder.gen.modular.composition.emit_app`, and the two
    are asserted byte-identical. Two composition roots that drift is the
    failure this shape exists to prevent.
    """
    features = spec.features
    notes = "\n".join("\n".join(textwrap.wrap(note, width=88)) for note in spec.notes)
    web_discover = [f"{package_name}.{root}" for root in ("controllers", "modules")]
    imports = [
        "from quadkit.app import Application",
        "from quadkit.config import QuadkitConfig",
    ]
    if "web" in features:
        imports.append(f"from {module_for('web')} import WebModule")
    if "graphql" in features:
        imports.append(f"from {module_for('graphql')} import GraphQLModule")
    local_imports = [
        f"from {package_name}.infrastructure import infrastructure_modules",
        f"from {package_name}.modules import MODULES",
    ]
    lines = [
        "    application.add_modules(",
        "        [",
        "            *infrastructure_modules(),",
    ]
    if "graphql" in features:
        lines.append("            GraphQLModule.configure(),")
    lines.append("            *MODULES,")
    if "web" in features:
        web_lines = _web_configure_lines(web_discover)
        web_lines[-1] = f"{web_lines[-1]},"
        lines.extend(f"            {line}" for line in web_lines)
    lines.append("        ]")
    lines.append("    )")
    imports.sort()
    local_imports.sort()
    import_lines = "\n".join(imports) + "\n\n" + "\n".join(local_imports)

    return f'''"""{project_name} - composition root.

{notes}
"""
from __future__ import annotations

{import_lines}


def create_app(config: "QuadkitConfig | None" = None) -> "Application":
    """Create the application in ``CREATED`` state (not yet started).

    Args:
        config: Optional pre-loaded config.  When ``None`` the framework
            auto-discovers ``application.yaml`` from the working directory.

    Returns:
        The bootable application instance.
    """
    application = Application(name="{project_name}", config=config)
{chr(10).join(lines)}
    return application


app = create_app()

__all__ = ["app", "create_app"]
'''


def _controller_module(project_name: str) -> str:
    return f'''"""Root API controllers.

`quadkit gen controller <name>` writes additional controllers into this
package; WebModule.configure(discover=["controllers"]) picks them up.

The framework already serves the canonical health probes at `/health`,
`/health/live`, `/health/ready`, and `/health/startup`; keep custom health
endpoints under a prefix such as `/api` so they do not shadow them.
"""
from __future__ import annotations

from typing import Any

from quadkit.web import Controller, get


class ApiController(Controller):
    """Root API endpoints."""

    @get("/")
    async def root(self) -> dict[str, Any]:
        """Service banner for the application root."""
        return {{"service": "{project_name}", "status": "ok"}}
'''


def _module_controller(package_name: str, module: str) -> str:
    """Sample controller for the modular ``users`` module."""
    return f'''"""Root API controllers for the {module} module.

`quadkit gen controller <name> --module {module}` writes additional
controllers here; WebModule.configure(discover=["{package_name}.modules"])
picks them up.
"""
from __future__ import annotations

from typing import Any

from quadkit.web import Controller, get


class ApiController(Controller):
    """Root API endpoints."""

    @get("/")
    async def root(self) -> dict[str, Any]:
        """Service banner for the application root."""
        return {{"service": "{package_name}", "status": "ok"}}
'''


def _conftest(project_name: str, package_name: str, spec: ProjectTemplateSpec) -> str:
    extras: list[str] = []
    if "web" in spec.features:
        extras = [
            "from quadkit.web import WebProvider",
            "from starlette.applications import Starlette",
        ]
    web_fixture = ""
    if "web" in spec.features:
        web_fixture = '''

@pytest.fixture
async def app(application: Application) -> Starlette:
    """Expose the Starlette app for httpx ASGI tests."""
    web = await application.container.resolve(WebProvider)
    return web.starlette
'''
    import_lines = [
        "import os",
        "import sys",
        "from pathlib import Path",
        "",
        "import pytest",
        "from quadkit.app import Application",
    ]
    import_lines.extend(extras)
    return f'''"""Pytest bootstrap for {project_name}."""
from __future__ import annotations

{chr(10).join(import_lines)}

_ROOT = Path(__file__).resolve().parents[1]
os.chdir(_ROOT)
sys.path.insert(0, str(_ROOT / "src"))

from {package_name}.app import create_app  # noqa: E402


@pytest.fixture
async def application() -> Application:
    """Boot the application for the duration of a test."""
    application = create_app()
    await application.start()
    try:
        yield application
    finally:
        await application.stop()
{web_fixture}
'''
