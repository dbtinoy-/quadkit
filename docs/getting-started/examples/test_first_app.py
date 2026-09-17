"""Runnable companion to docs/getting-started/testing.md.

Tests for first_app.py — run from this directory with::

    python -m pytest test_first_app.py -v

pytest-asyncio ships with quadkit-testing; the marker below makes async
tests work whether a project enables asyncio auto-mode or not.
"""

import pytest

from first_app import create_app
from quadkit.testing import WebTestBed


@pytest.mark.asyncio
async def test_hello_default_name() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/hello")
        response.assert_status(200)
        assert response.json == {"message": "hello, world"}


@pytest.mark.asyncio
async def test_hello_with_name() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/hello", params={"name": "quadkit"})
        response.assert_status(200)
        assert response.json == {"message": "hello, quadkit"}


@pytest.mark.asyncio
async def test_docs_endpoint_is_free() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/docs")
        response.assert_status(200)
        assert "text/html" in response.headers.get("content-type", "")
