"""Pytest bootstrap for the example-hub demo."""

from __future__ import annotations

from collections.abc import AsyncIterator
import os
from pathlib import Path
import sys

import httpx
import pytest
from starlette.applications import Starlette

_DEMO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_DEMO_ROOT / "src"))


@pytest.fixture
async def app() -> AsyncIterator[Starlette]:
    """Boot the hub composition root and expose its ASGI app."""
    from example_hub.app import create_app

    application = create_app()
    await application.start()
    try:
        from quadkit.web.di.provider import WebProvider

        web = await application.container.resolve(WebProvider)
        yield web.starlette
    finally:
        await application.stop()


@pytest.fixture
async def client(app: Starlette) -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP client wired to the in-process ASGI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        yield http


@pytest.fixture(autouse=True)
def _ensure_cwd() -> None:
    """Pin cwd to the demo root before every test."""
    os.chdir(_DEMO_ROOT)
