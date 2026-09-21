"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the Auth Tokens demo: token login with HMAC-signed
bearer tokens (no JWT dependency), protected routes, and DI-injected auth.
"""

from __future__ import annotations

from auth_tokens.controllers.api import SessionController
from auth_tokens.di.provider import AuthTokensProvider
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the Auth Tokens demo."""
    return [WebModule.configure(controllers=[SessionController])]


def build_providers() -> list[Provider]:
    """Build the DI providers for the Auth Tokens demo."""
    return [AuthTokensProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the Auth Tokens application."""
    app = Application(name="auth-tokens", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
