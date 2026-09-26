"""Convention followed: **Composition root** — one file knows how modules, providers and controllers fit; ``create_app(config=...)`` is the injection seam.

Composition root for the api-keys demo — start reading here.

Every Quadkit application has exactly one place that knows how the pieces
fit together: the **composition root**.  Everything else (controllers,
services, templates) is inert until *this file* wires it.

The mental model has three layers.  Once these click, every Quadkit app
reads the same way:

┌─────────────────────────────────────────────────────────────────────────┐
│ 1. CONFIGURATION                                                        │
│    ``application.yaml`` holds your values.  The framework loads it,     │
│    merges overrides on top (highest → lowest):                          │
│                                                                         │
│        QK_WEB__SERVER__PORT=9000   env vars   ← win over everything    │
│        application.production.yaml  profile overlay                     │
│        application.yaml             base file                           │
│        dataclass field defaults     last resort                         │
│                                                                         │
│    Result: ONE typed ``QuadkitConfig`` object.                         │
│                                                                         │
│ 2. CAPABILITIES (declarative)                                           │
│    ``Module.configure(...)`` switches framework packages on and tells   │
│    them which controllers are yours.  Each package reads its own yaml   │
│    section through its config model.                                    │
│                                                                         │
│ 3. SERVICES (imperative)                                               │
│    A ``Provider`` registers the services *you* wrote into the DI        │
│    container, with register/boot/shutdown lifecycle hooks.              │
└─────────────────────────────────────────────────────────────────────────┘

Two wiring styles are supported everywhere; both produce identical
runtime behavior:

- **Explicit** (this file): sections passed to ``configure(config=...)``

Run with::

    cd examples/auth-apikeys
    PYTHONPATH=src uv run python -m apikey_console
"""
# Quadkit composition root — the single file that wires
# all modules and providers together. Your app will have exactly one
# composition root. Framework modules (AuthModule, WebModule) are
# declarative; your app-specific Provider is imperative.

from __future__ import annotations

from apikey_console.controllers.api import KeysApiController
from apikey_console.di.provider import ApiKeysProvider
from apikey_console.ui.pages import PagesController
from quadkit.app.base import Application
from quadkit.auth.module import AuthModule
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Declarative capabilities — zero configuration arguments needed.

    Each ``Module.configure()`` (no args) reads its typed section from
    application.yaml automatically via config_key/config_model on the
    module's providers.  Override per-provider if needed.
    """
    # Module.configure() auto-reads its yaml section.
    # No manual config passing — the framework discovers the config_key
    # from each provider. AuthModule reads `auth:`, WebModule reads `web:`.
    return [
        # Auth: users, roles, RBAC, JWT, password rules.
        # Reads ``auth:`` from application.yaml automatically.
        AuthModule.configure(),
        # Web: Starlette server + middleware.  Controllers are your HTTP
        # surface.  Omit PagesController + delete ui/ if using
        # an external frontend.
        WebModule.configure(
            controllers=[KeysApiController, PagesController],
        ),
    ]


def build_providers() -> list[Provider]:
    """Imperative services owned by this demo."""
    return [ApiKeysProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create the application in ``CREATED`` state (not yet started).

    Use this in tests (boot it yourself) or hand to ``main.py`` which
    calls ``app.start()`` / ``app.stop()``.

    Args:
        config: Optional pre-loaded config. When ``None`` the framework
            auto-discovers ``application.yaml`` from the working directory.
    """
    # Application is created, modules+providers added,
    # but not yet started. Tests use this to boot the app manually.
    app = Application(name="apikeys-console", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
