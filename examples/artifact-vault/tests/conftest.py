"""Pytest bootstrap for Artifact Vault."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

from artifact_vault.app import build_providers  # noqa: E402
from artifact_vault.controllers.api import ArtifactVaultApiController  # noqa: E402
from artifact_vault.di.provider import ArtifactVaultProvider  # noqa: E402
from artifact_vault.ui.pages import ArtifactVaultPageController  # noqa: E402
from quadkit.app.base import Application  # noqa: E402
from quadkit.storage.module import StorageModule  # noqa: E402
from quadkit.web import WebProvider  # noqa: E402
from quadkit.web.module import WebModule  # noqa: E402


@pytest.fixture(autouse=True)
def _ensure_cwd() -> None:
    os.chdir(ROOT)


@pytest.fixture
async def app() -> AsyncIterator[Starlette]:
    application = Application(name="artifact-vault")
    application.add_modules([
        StorageModule.stub(),
        WebModule.configure(
            controllers=[ArtifactVaultApiController, ArtifactVaultPageController],
        ),
    ])
    application.add_providers([ArtifactVaultProvider()])
    await application.start()
    try:
        web = await application.container.resolve(WebProvider)
        yield web.starlette
    finally:
        await application.stop()


@pytest.fixture
async def client(app: Starlette) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as http:
        yield http
