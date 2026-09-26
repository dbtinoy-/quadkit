"""Convention followed: **Composition root** — one file knows how modules, providers and controllers fit; ``create_app(config=...)`` is the injection seam.

Composition root for the event-driven orders demo — start reading here.

Every Quadkit application has exactly one place that knows how the pieces
fit together: the **composition root**.  Everything else (controllers,
services, templates) is inert until *this file* wires it.

The mental model has three layers.  Once these click, every Quadkit app
reads the same way:

1. CONFIGURATION — ``application.yaml`` holds your values.  The framework
   loads it; ``QK_*`` env vars win over yaml.

2. CAPABILITIES (declarative) — ``Module.configure(...)`` switches
   framework packages on.  Each reads its own yaml section automatically.

3. SERVICES (imperative) — a ``Provider`` registers the services *you*
   wrote into the DI container.

This demo's lesson is the **CQRS + outbox** pattern: commands flow through
the command bus, handlers persist state and stage domain events in the
outbox, and the outbox relay delivers events to read-side projections and
notification handlers.  The REST surface and browser UI drive the same
``OrdersApi`` facade.

Run with::

    cd examples/event-driven-orders
    PYTHONPATH=src uv run python -m orders
"""
# Quadkit composition root — the single file that wires
# all modules and providers together. Your app will have exactly one
# composition root. Framework modules (EventsModule, WebModule) are
# declarative; your app-specific Provider is imperative.

from __future__ import annotations

from orders.controllers.api import OrdersApiController
from orders.di.provider import OrdersProvider
from orders.ui.pages import OrdersPageController
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.events.module import EventsModule
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Declarative capabilities — zero configuration arguments needed.

    Each ``Module.configure()`` (no args) reads its typed section from
    application.yaml automatically via config_key/config_model on the
    module's providers.  Override per-provider if needed.
    """
    return [
        # Events: command bus, event bus, domain events.
        # No config argument -> framework defaults: in-memory event store.
        EventsModule.configure(),
        # Web: Starlette server + middleware.  Controllers are your HTTP
        # surface.  Omit OrdersPageController + delete ui/ if using
        # an external frontend.
        WebModule.configure(
            controllers=[OrdersApiController, OrdersPageController],
        ),
    ]


def build_providers() -> list[Provider]:
    """Imperative services owned by this demo."""
    return [OrdersProvider()]


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
    app = Application(name="event-driven-orders", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
