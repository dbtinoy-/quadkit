"""Convention followed: **Composition root** — one file knows how modules, providers and controllers fit; ``create_app(config=...)`` is the injection seam.

Composition root for the sql-repository demo — start reading here.

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
│        QK_DEMO__KEY=value  env vars  ← win                            │
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

Run with::

    PYTHONPATH=src uv run python -m taskapp
"""

from __future__ import annotations

from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.sql.config import DatabaseConfig
from quadkit.sql.module import DatabaseModule
from quadkit.web.module import WebModule
from taskapp.controllers.api import TasksApiController
from taskapp.di.provider import TaskProvider
from taskapp.ui.pages import TasksPageController


def build_modules() -> list[object]:
    """Declarative capabilities — zero configuration arguments needed.

    Each ``Module.configure(...)`` returns a DynamicModule: a recipe the
    framework expands into providers at boot.  Because every provider in
    the bundle declares ``config_key`` / ``config_model``, the orchestrator
    injects the matching typed section of ``QuadkitConfig`` into
    ``provider.config`` right before ``register()`` runs — YAML values and
    ``QK_*`` environment overrides already merged.
    """
    return [
        # DatabaseModule owns SQLite connection lifecycle and exposes the
        # DatabaseProviderProtocol used by this demo's task repository.
        DatabaseModule.configure(
            DatabaseConfig.from_url("sqlite+aiosqlite:///:memory:")
        ),
        WebModule.configure(
            controllers=[TasksApiController, TasksPageController],
        ),
    ]


def build_providers() -> list[Provider]:
    """Imperative services owned by this demo.

    A Provider is Quadkit's unit of lifecycle management: ``register()``
    binds services into the DI container, ``boot()`` runs post-registration
    setup, ``shutdown()`` cleans up.
    """
    return [TaskProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create the application in ``CREATED`` state (not yet started).

    Accepts an optional ``QuadkitConfig`` for scenarios where the config
    is loaded explicitly (e.g. hub mounting).  When called standalone,
    the framework auto-discovers ``application.yaml`` from the working
    directory.

    Use this directly in tests (boot it yourself so you control the
    lifecycle) or hand the pieces to :meth:`Application.start` as
    ``main.serve`` does — the ``finally`` block ensures ``stop()`` runs
    even when something raises.

    Args:
        config: Optional pre-loaded config. When ``None`` the framework
            auto-discovers ``application.yaml`` from the working directory.
    """
    # Application is created in CREATED state — not yet started.
    # Modules declare capabilities; providers fill services.
    # The dependency graph resolves lazily at boot.
    app = Application(name="sql-repository", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
