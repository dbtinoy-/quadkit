"""Pytest bootstrap for the auth web demo.

Two jobs:

1. Make imports and config discovery work regardless of *where* pytest is
   invoked: chdir into this demo's root (where ``application.yaml`` lives)
   and put ``src`` on ``sys.path``. The framework auto-discovers
   ``application.yaml`` from the working directory, so after this chdir no
   custom configuration loader is needed anywhere.
2. Boot the real composition root for tests via fixtures.

    uv run pytest examples/auth-web/tests -q        # from repo root works too
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import os
from pathlib import Path
import sys

import httpx
import pytest
from starlette.applications import Starlette

_DEMO_ROOT = Path(__file__).resolve().parent

# Quadkit discovers application.yaml from cwd — pin it so tests work
# from any invocation point (repo root or in-demo).
os.chdir(_DEMO_ROOT)
# Add src/ to sys.path so ``from auth_web...`` resolves in tests.
sys.path.insert(0, str(_DEMO_ROOT / "src"))

from auth_web.app import create_app  # noqa: E402 — after sys.path setup

from quadkit.web.di.provider import WebProvider  # noqa: E402


@pytest.fixture(autouse=True)
def _ensure_cwd() -> None:
    """Pin cwd to the demo root before every test."""
    os.chdir(_DEMO_ROOT)


@pytest.fixture
async def app() -> AsyncIterator[Starlette]:
    """Boot the real composition root; yield the Starlette ASGI app."""
    application = create_app()
    await application.start()
    try:
        web = await application.container.resolve(WebProvider)
        yield web.starlette
    finally:
        await application.stop()


@pytest.fixture
async def client(app: Starlette) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client bound to the app with a cookie jar per test."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        yield http
