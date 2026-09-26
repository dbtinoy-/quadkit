"""Convention followed: **Composition root** — one file knows how modules, providers and controllers fit; ``create_app(config=...)`` is the injection seam.

Composition root for the single-niche Artifact Vault demo."""

from __future__ import annotations

from artifact_vault.controllers.api import ArtifactVaultApiController
from artifact_vault.di.provider import ArtifactVaultProvider
from artifact_vault.ui.pages import ArtifactVaultPageController
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.storage.module import StorageModule
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the artifact vault demo."""
    return [
        StorageModule.configure(),
        WebModule.configure(
            controllers=[ArtifactVaultApiController, ArtifactVaultPageController],
        ),
    ]


def build_providers() -> list[Provider]:
    """Build the DI providers for the artifact vault demo."""
    return [ArtifactVaultProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the artifact vault application."""
    app = Application(name="artifact-vault", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
