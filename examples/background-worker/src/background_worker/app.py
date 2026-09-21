"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the Background Worker demo: long-running work off
the request path with an asyncio queue, bounded concurrency, graceful
shutdown, and an HTTP facet for submitting and observing work.
"""

from __future__ import annotations

from background_worker.controllers.api import WorkController
from background_worker.di.provider import BackgroundWorkerProvider
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the Background Worker demo."""
    return [WebModule.configure(controllers=[WorkController])]


def build_providers() -> list[Provider]:
    """Build the DI providers for the Background Worker demo."""
    return [BackgroundWorkerProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the Background Worker application."""
    app = Application(name="background-worker", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
