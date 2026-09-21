"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the Minimal API demo: the smallest useful Quadkit
web service — one controller, two routes, one module, one provider.
"""

from __future__ import annotations

from minimal_api.controllers.api import HelloController
from minimal_api.di.provider import MinimalApiProvider
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the Minimal API demo."""
    return [WebModule.configure(controllers=[HelloController])]


def build_providers() -> list[Provider]:
    """Build the DI providers for the Minimal API demo."""
    return [MinimalApiProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the Minimal API application."""
    app = Application(name="minimal-api", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
