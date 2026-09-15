"""Pytest bootstrap for the storefront demo."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette

_DEMO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_DEMO_ROOT)
sys.path.insert(0, str(_DEMO_ROOT / "src"))

from quadkit.web import WebProvider  # noqa: E402
from storefront.app import create_app  # noqa: E402


@pytest.fixture
async def app() -> AsyncIterator[Starlette]:
    application = create_app()
    await application.start()
    try:
        web = await application.container.resolve(WebProvider)
        yield web.starlette
    finally:
        await application.stop()


@pytest.fixture
async def client(app: Starlette) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        yield http


@pytest.fixture(autouse=True)
def _ensure_cwd() -> None:
    os.chdir(_DEMO_ROOT)
