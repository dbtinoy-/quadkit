"""Unit tests for ``InvalidatingCacheMixin`` / ``CachedRepositoryMixin``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.cache.repository import CachedRepositoryMixin, InvalidatingCacheMixin
from quadkit.contracts.core import Err, Ok


class _Repo(CachedRepositoryMixin):
    cache_prefix = "pet"
    cache_ttl = 120

    def __init__(self, cache: object) -> None:
        self._cache = cache


@pytest.mark.asyncio
async def test_cached_get_unwraps_ok_result() -> None:
    assert CachedRepositoryMixin is InvalidatingCacheMixin
    backend = AsyncMock()
    backend.get.return_value = Ok({"id": "p1"})
    repo = _Repo(backend)
    loader = AsyncMock(return_value={"id": "fresh"})

    value = await repo._cached_get("p1", loader)
    assert value == {"id": "p1"}
    loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_get_falls_back_on_miss_or_err_and_invalidates() -> None:
    backend = AsyncMock()
    backend.get.return_value = Err(RuntimeError("cache down"))
    repo = _Repo(backend)
    loader = AsyncMock(return_value={"id": "p2"})

    value = await repo._cached_get("p2", loader)
    assert value == {"id": "p2"}
    backend.set.assert_awaited_once_with("pet:p2", {"id": "p2"}, ttl=120)

    await repo._invalidate("p2")
    backend.delete.assert_awaited_once_with("pet:p2")

    await repo._invalidate_list()
    backend.delete_pattern.assert_awaited_once_with("pet:list:*")
