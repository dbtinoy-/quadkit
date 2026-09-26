"""Convention followed: **Composition root** — one file knows how modules, providers and controllers fit; ``create_app(config=...)`` is the injection seam.

Composition root for the focused Events Timeline / Replay Lab."""

from __future__ import annotations

from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.events.module import EventsModule
from quadkit.web.module import WebModule
from timeline_lab.controllers.api import TimelineApiController
from timeline_lab.di.provider import TimelineLabProvider
from timeline_lab.ui.pages import TimelinePageController


def build_modules() -> list[object]:
    """Enable only the package under test and its browser transport."""
    return [
        EventsModule.configure(),
        WebModule.configure(
            controllers=[TimelineApiController, TimelinePageController],
        ),
    ]


def build_providers() -> list[Provider]:
    """Register the demo scenario's lifecycle wiring."""
    return [TimelineLabProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create an unstarted application for standalone use and tests."""
    application = Application(name="event-timeline", config=config)
    application.add_modules(build_modules())
    application.add_providers(build_providers())
    return application


__all__ = ["build_modules", "build_providers", "create_app"]
