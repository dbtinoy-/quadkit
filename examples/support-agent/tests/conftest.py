"""Pytest bootstrap for the support-agent demo.

Two jobs:

1. Make imports and config discovery work regardless of *where* pytest is
   invoked: chdir into this demo's root (where ``application.yaml`` lives)
   and put ``src`` on ``sys.path``. The framework auto-discovers
   ``application.yaml`` from the working directory, so after this chdir no
   custom configuration loader is needed anywhere.
2. Boot the real composition root for tests via fixtures.

    uv run pytest examples/support-agent/tests -q        # from repo root works too
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import os
from pathlib import Path
import sys

import httpx
import pytest
from starlette.applications import Starlette

_DEMO_ROOT = Path(__file__).resolve().parent.parent

# Quadkit discovers application.yaml from cwd — pin it so tests work
# from any invocation point (repo root or in-demo).
os.chdir(_DEMO_ROOT)
# Add src/ to sys.path so ``from support_agent...`` resolves in tests.
sys.path.insert(0, str(_DEMO_ROOT / "src"))


@pytest.fixture(autouse=True)
def _ensure_cwd() -> None:
    """Pin CWD to demo root for every test (framework reads application.yaml from cwd)."""
    os.chdir(_DEMO_ROOT)


@pytest.fixture
async def app() -> AsyncIterator[Starlette]:
    """Boot the real composition root and expose its ASGI app."""
    from support_agent.app import create_app

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
    """HTTP client over the running app (no socket bound)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        yield http
