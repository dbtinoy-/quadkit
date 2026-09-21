"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=..., client=...)`` is
the injection seam.

Composition root for the AI Assistant demo: an external-integration
starter — Quadkit ships no AI client, so the demo shows the seam. The
controller depends on the ``AssistantClient`` protocol; the provider
binds an OpenAI-compatible HTTP client in production and accepts a fake
in tests.
"""

from __future__ import annotations

from ai_assistant.controllers.api import ChatController
from ai_assistant.di.provider import AIAssistantProvider
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the AI Assistant demo."""
    return [WebModule.configure(controllers=[ChatController])]


def build_providers() -> list[Provider]:
    """Build the DI providers for the AI Assistant demo."""
    return [AIAssistantProvider()]


def create_app(
    config: QuadkitConfig | None = None, client: object | None = None
) -> Application:
    """Create and configure the AI Assistant application.

    ``client`` is the test seam: pass any ``AssistantClient`` fake and it
    is bound instead of the real HTTP client.
    """
    app = Application(name="ai-assistant", config=config)
    app.add_modules(build_modules())
    app.add_providers([AIAssistantProvider(client)])
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
