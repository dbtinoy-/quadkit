"""Route registry hygiene: no two registered routes may share a path.

The relay-gateway contributor once registered GET /health before the
canonical web health route (fixed by registering /health pre-contributors);
this test keeps first-match-wins collisions impossible to reintroduce.
"""

from __future__ import annotations

from collections import Counter

import pytest

from quadkit.web.di.provider import WebProvider


@pytest.mark.asyncio
async def test_no_duplicate_route_paths(test_bed) -> None:
    """Every registered Starlette route path must be unique."""

    web = await test_bed.resolve(WebProvider)
    paths = [
        path
        for path in (getattr(route, "path", None) for route in web.starlette.routes)
        if path
    ]
    duplicates = {path: count for path, count in Counter(paths).items() if count > 1}
    assert not duplicates, f"duplicate route paths registered: {duplicates}"
