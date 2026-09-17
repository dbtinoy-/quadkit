"""Pytest bootstrap for the Auth Tokens demo.

Two jobs:

1. Make imports and config discovery work regardless of *where* pytest is
   invoked: chdir into this demo's root (where ``application.yaml`` lives)
   and put ``src`` on ``sys.path``.
2. Expose the booted app and an ``httpx`` client wired to its ASGI
   surface, so tests exercise real round trips — no server, no mocks.
"""

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

from quadkit.web import WebProvider  # noqa: E402

from auth_tokens.app import create_app  # noqa: E402


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
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as http:
        yield http


@pytest.fixture(autouse=True)
def _ensure_cwd() -> None:
    os.chdir(ROOT)
