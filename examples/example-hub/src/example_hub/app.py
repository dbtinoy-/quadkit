"""Convention followed: **Composition root** — one file knows how modules, providers and controllers fit; ``create_app(config=...)`` is the injection seam.

Composition root for the demo hub — start reading here.

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
  make the wiring visible and testable at the composition root.
- **Automatic**: call ``configure()`` with no arguments — providers declare
  ``config_key``/``config_model``, so the orchestrator injects their typed
  section from the loaded config before boot.

Unknown/typo keys (``prot:`` vs ``port:``) fail startup with a
did-you-mean suggestion instead of silently falling back to defaults.

The hub is a **meta-demo**: it boots every web demo's real Quadkit
``Application`` in-process and mounts it under ``/examples/<slug>/``.
The ``Fleet`` service handles child mounting; this file wires the hub
itself.

Run with::

    PYTHONPATH=src uv run python -m example_hub
"""

from __future__ import annotations

from example_hub.controllers.api import HubApiController  # your HTTP surface
from example_hub.di.provider import HubProvider  # your service registrations
from example_hub.ui.pages import HubPageController  # page controller (optional)
from quadkit.app.base import Application  # Application = the bootable object
from quadkit.di.provider import Provider  # base class for your DI registrations
from quadkit.web.module import WebModule  # framework module — owns web server

# Quadkit follows a strict dependency direction: application code imports
# framework packages, never the reverse.  This file is the only place
# that references both framework modules AND your controllers/providers.


def build_modules() -> list[object]:
    """Declarative capabilities — zero configuration arguments needed.

    Each ``Module.configure(...)`` returns a DynamicModule: a recipe the
    framework expands into providers at boot.  Because every provider in
    the bundle declares ``config_key`` / ``config_model``, the orchestrator
    injects the matching typed section of ``WebConfig`` into
    ``provider.config`` right before ``register()`` runs — YAML values and
    ``QK_*`` environment overrides already merged.
    """
    return [
        # WebModule is the only module that needs your controllers list —
        # this is the explicit wiring style.  Omit HubPageController if you
        # use an external frontend (React, Vue, etc.).
        WebModule.configure(
            controllers=[HubApiController, HubPageController],
        ),
    ]


def build_providers() -> list[Provider]:
    """Imperative services owned by this demo.

    A Provider is Quadkit's unit of lifecycle management: ``register()``
    binds services into the DI container, ``boot()`` runs post-registration
    setup (here: mounting child demos via Fleet), ``shutdown()`` cleans up.
    """
    return [HubProvider()]


def create_app(config: object | None = None) -> Application:
    """Create the application in ``CREATED`` state (not yet started).

    Accepts an optional ``QuadkitConfig`` for child-mounting scenarios
    (the Fleet passes each child's own config).  When called standalone,
    the framework auto-discovers ``application.yaml`` from the working
    directory.

    Use this directly in tests (boot it yourself so you control the
    lifecycle) or hand the pieces to :meth:`Application.boot` as
    ``main.serve`` does — the context manager guarantees ``stop()`` even
    when something raises.
    """
    # Application is created in CREATED state — not yet started.
    # Modules declare capabilities; providers fill services.
    # The dependency graph resolves lazily at boot.
    kwargs: dict[str, object] = {"name": "example-hub"}
    if config is not None:
        kwargs["config"] = config
    app = Application(**kwargs)  # type: ignore[arg-type]
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
