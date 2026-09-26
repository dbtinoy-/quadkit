"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the Cache-Aside demo: a Quadkit web service that reads
through ``quadkit-cache`` — a report is computed once and served from the
cache until it is invalidated.
"""

from __future__ import annotations

from cache_side.controllers.api import ReportController
from cache_side.di.provider import CacheSideProvider
from quadkit.app.base import Application
from quadkit.cache.config import CacheBackendConfig, CacheConfig
from quadkit.cache.module import CacheModule
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the Cache-Aside demo.

    The cache is configured explicitly with a single in-memory backend so the
    demo runs with no external service; a real deployment would read the
    ``cache:`` yaml section instead (see ``examples/resilient-rates``).
    """
    cache_config = CacheConfig(
        backends=[
            CacheBackendConfig(
                name="default",
                type="memory",
                default=True,
                default_ttl=60,
            )
        ]
    )
    return [
        CacheModule.configure(cache_config),
        WebModule.configure(controllers=[ReportController]),
    ]


def build_providers() -> list[Provider]:
    """Build the DI providers for the Cache-Aside demo."""
    return [CacheSideProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the Cache-Aside application."""
    app = Application(name="cache-aside", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
