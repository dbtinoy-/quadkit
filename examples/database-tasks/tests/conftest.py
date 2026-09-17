"""Pytest bootstrap for the Database Tasks demo.

Two jobs:

1. Make imports and config discovery work regardless of *where* pytest is
   invoked: chdir into this demo's root (where ``application.yaml`` lives)
   and put ``src`` on ``sys.path``.
2. Expose the booted app and an ``httpx`` client wired to its ASGI
   surface, so tests exercise real round trips — no server, no mocks.
   Each test gets a throwaway SQLite file via the typed-config env
   override (``QK_DATABASE_TASKS__DB_PATH``), the same knob production
   would set.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

from quadkit.web import WebProvider  # noqa: E402

from database_tasks.app import create_app  # noqa: E402


@pytest.fixture
async def app(tmp_path: Path) -> AsyncIterator[Starlette]:
    os.environ["QK_DATABASE_TASKS__DB_PATH"] = str(tmp_path / "tasks.db")
    try:
        application = create_app()
        await application.start()
        try:
            web = await application.container.resolve(WebProvider)
            yield web.starlette
        finally:
            await application.stop()
    finally:
        os.environ.pop("QK_DATABASE_TASKS__DB_PATH", None)


@pytest.fixture
async def client(app: Starlette) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as http:
        yield http


@pytest.fixture(autouse=True)
def _ensure_cwd() -> None:
    os.chdir(ROOT)
