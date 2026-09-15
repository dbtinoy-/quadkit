"""Bounded-context modules for the storefront demo.

Convention followed: **Modules index** (Pattern 3, "Modular App Layout") —
builds every bounded context, already ``.configure()``d, in dependency
order so the composition root (``storefront.app``) can wire them with a
single ``add_modules(build_modules())`` call.

This is a function rather than a module-level constant on purpose: each
``.configure()`` call constructs fresh ``Provider`` instances, and a
``Provider`` carries mutable lifecycle state (``CREATED`` ->
``REGISTERED`` -> ``BOOTED`` -> ``SHUTDOWN``). A module-level list built
once at import time would hand out the *same* provider instances to
every ``create_app()`` call in a process — harmless for a single running
app, but fatal for a test suite that boots and stops the application
repeatedly, since the second boot would see already-``SHUTDOWN``
providers.

Exports:

- ``build_modules`` — returns a fresh, ordered list of configured modules
  for ``Application.add_modules()``
"""

from __future__ import annotations

from storefront.modules.catalog import CatalogModule
from storefront.modules.orders import OrdersModule


def build_modules() -> list[object]:
    """Return freshly configured bounded-context modules, dependency-ordered.

    ``orders`` imports the same ``CatalogModule`` ``DynamicModule``
    instance built here rather than creating its own via a second
    ``CatalogModule.configure()`` call — the compiler rejects two
    independent configurations of the same module class as
    ``ModuleDuplicateError``.
    """
    catalog = CatalogModule.configure()
    return [catalog, OrdersModule.configure(catalog=catalog)]


__all__ = ["build_modules"]
