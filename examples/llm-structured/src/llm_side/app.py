"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the LLM Structured Output demo on ``quadkit-ai-llm``.
"""

from __future__ import annotations

from llm_side.controllers.api import TicketExtractionController
from llm_side.di.provider import LlmSideProvider
from quadkit.ai.llm import LLMModule
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Compose ``LLMModule`` and ``WebModule``.

    ``LLMModule.stub()`` registers the LLM subsystem cleanly without requiring
    cloud credentials; ``LlmSideProvider`` then binds a deterministic
    schema-aware ``LLMClientProtocol`` for repeatable offline extraction.
    """
    return [
        LLMModule.stub(),
        WebModule.configure(controllers=[TicketExtractionController]),
    ]


def build_providers() -> list[Provider]:
    """Build the DI providers for the LLM Structured Output demo."""
    return [LlmSideProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the LLM Structured Output application."""
    app = Application(name="llm-structured", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
