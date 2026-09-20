"""Canonical Quadkit project scaffold.

Single source of truth for project bootstrapping — the catalogue lives in
:mod:`quadkit.cli.scaffold.specs`, the rendered files in
:mod:`quadkit.cli.scaffold.app_files`, :mod:`quadkit.cli.scaffold.module_files`
and :mod:`quadkit.cli.scaffold.support_files`, and the writers in
:mod:`quadkit.cli.scaffold.render`:

- ``quadkit new project --template <name>`` (``commands/new.py``)
- ``ProjectBuilder.create_project`` (``registry/template.py``)
- scaffold alignment tests (``tests/unit/test_scaffold_alignment.py``)

Every generated file targets the **real** quadkit APIs (``Application``,
``QuadkitConfig``, ``WebModule``, ``Controller``) and the **canonical
generator map** in :mod:`quadkit.cli.layout`, so a scaffolded project and
its generators stay aligned:

    quadkit new project myapp --template web-api
    cd myapp && pip install -e .
    quadkit gen controller users  # src/myapp/controllers/users_controller.py
    quadkit dev                   # WebModule auto-discovers it

There is one project layout. A project starts flat -- feature components sit
directly under ``src/<app>/`` -- and grows bounded contexts in place:
``quadkit new module billing`` adds ``src/<app>/modules/billing/``, and
``quadkit gen controller orders --module billing`` writes into it. Nothing
about the project changes when that happens; only the generated node moves.
Cross-cutting components always live under ``src/<app>/shared/``.

The generated ``application.yaml`` is validated by :class:`QuadkitConfig`
(extra sections such as ``web`` / ``sql`` are consumed through the
``quadkit.config`` entry-point registry), and ``create_app()`` is a
standard composition root: bootable via ``quadkit dev`` / ``quadkit run``
and directly in pytest fixtures.
"""

from __future__ import annotations

from quadkit.cli.scaffold.render import render_module, render_project
from quadkit.cli.scaffold.specs import (
    _TEMPLATE_SPECS,
    TEMPLATE_ALIASES,
    TEMPLATES,
    ProjectTemplateSpec,
    component_packages,
    resolve_template,
    root_output_dirs,
    template_names,
)

__all__ = [
    "TEMPLATES",
    "component_packages",
    "render_module",
    "render_project",
    "resolve_template",
    "root_output_dirs",
    "template_names",
]
