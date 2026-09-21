"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the Multi-Tenant Notes demo: tenant resolution from
the ``X-Tenant-Id`` header and strict data isolation — every store
operation is keyed by tenant, so cross-tenant reads are impossible by
construction (not by convention).
"""

from __future__ import annotations

from multi_tenant_notes.controllers.api import NotesController
from multi_tenant_notes.di.provider import MultiTenantNotesProvider
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the Multi-Tenant Notes demo."""
    return [WebModule.configure(controllers=[NotesController])]


def build_providers() -> list[Provider]:
    """Build the DI providers for the Multi-Tenant Notes demo."""
    return [MultiTenantNotesProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the Multi-Tenant Notes application."""
    app = Application(name="multi-tenant-notes", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
