"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the HTTP Client demo: a Quadkit web service that makes
outbound calls with ``quadkit-http``'s client against an in-process mock
upstream — a real loopback round-trip, no third party, no resilience layer.
"""

from __future__ import annotations

from http_side.controllers.api import UpstreamController
from http_side.di.provider import HttpSideProvider
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.http.module import HTTPModule
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the HTTP Client demo."""
    return [
        HTTPModule.configure(),
        WebModule.configure(controllers=[UpstreamController]),
    ]


def build_providers() -> list[Provider]:
    """Build the DI providers for the HTTP Client demo."""
    return [HttpSideProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the HTTP Client application."""
    app = Application(name="http-client", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
