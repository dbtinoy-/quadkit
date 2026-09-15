"""Multi-module storefront demo — bounded contexts teaching artifact.

Convention followed: **Package exports** — ``__init__.py`` re-exports the
public API surface without defining logic.

This is the framework's first **multi-module** demo (see
``docs/getting-started/project-structure.md`` — Pattern 3, "Modular App
Layout"). Every other demo in ``examples/`` is a single flat package; this
one grows two bounded contexts under ``storefront/modules/`` — ``catalog``
and ``orders`` — that talk to each other only through a protocol exported
from ``catalog``'s ``@module`` boundary, never through a direct import of
its implementation.

Exports:

- ``create_app`` — composition root for the application
"""

from __future__ import annotations

from storefront.app import create_app

__all__ = ["create_app"]
