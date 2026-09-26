"""Convention followed: **Composition root** — one file knows how modules, providers and controllers fit; ``create_app(config=...)`` is the injection seam.

Application composition root for the auth web demo.

Every Quadkit application has exactly one place that knows how the pieces
fit together: the composition root.  Everything else (controllers,
services, views) is inert until this file wires it.

``application.yaml`` lives next to this demo's root; the framework
auto-discovers it from the working directory.  No explicit config loading
is needed — ``AuthModule.configure()`` and ``WebModule.configure()``
read their typed sections from the loaded config via ``config_key`` /
``config_model``.
"""

from __future__ import annotations

from auth_web.controllers.api import AuthApiController
from auth_web.di.provider import AuthWebProvider
from auth_web.ui.pages import PagesController
from quadkit.app.base import Application
from quadkit.auth.module import AuthModule
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Declarative capabilities — zero configuration arguments needed.

    Each ``Module.configure(...)`` returns a DynamicModule: a recipe the
    framework expands into providers at boot.  Because every provider in
    the bundle declares ``config_key`` / ``config_model``, the orchestrator
    injects the matching typed section of ``QuadkitConfig`` into
    ``provider.config`` right before ``register()`` runs.
    """
    return [
        AuthModule.configure(),
        WebModule.configure(
            controllers=[AuthApiController, PagesController],
        ),
    ]


def build_providers() -> list[Provider]:
    """Imperative services owned by this demo."""
    return [AuthWebProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create the application in CREATED state (not yet started).

    Modules declare capabilities; providers fill services.
    The dependency graph resolves lazily at boot.

    Args:
        config: Optional pre-loaded config. When ``None`` the framework
            auto-discovers ``application.yaml`` from the working directory.
    """
    app = Application(name="auth-web", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
