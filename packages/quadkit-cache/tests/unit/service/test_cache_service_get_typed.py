"""Tests for CacheService.get_typed typed retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.cache.service.core import CacheService


@dataclass
class _Point:
    x: int
    y: int


def _make_service(get_return_value: object) -> CacheService:
    mock_backend = AsyncMock()
    mock_backend.get = AsyncMock(return_value=get_return_value)
    provider = Mock()
    provider.get_backend.return_value = mock_backend
    return CacheService(provider)


class TestCacheServiceGetTypedHit:
    @pytest.mark.asyncio
    async def test_returns_existing_instance_unchanged(self) -> None:
        point = _Point(x=1, y=2)
        service = _make_service(point)

        result = await service.get_typed("pt", _Point)

        assert result is point

    @pytest.mark.asyncio
    async def test_constructs_from_dict(self) -> None:
        service = _make_service({"x": 3, "y": 7})

        result = await service.get_typed("pt", _Point)

        assert isinstance(result, _Point)
        assert result.x == 3
        assert result.y == 7

    @pytest.mark.asyncio
    async def test_constructs_from_scalar(self) -> None:
        service = _make_service("42")

        result = await service.get_typed("num", int)

        assert result == 42


class TestCacheServiceGetTypedMiss:
    @pytest.mark.asyncio
    async def test_returns_none_on_cache_miss(self) -> None:
        service = _make_service(None)

        result = await service.get_typed("missing", _Point)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_default_on_cache_miss(self) -> None:
        service = _make_service(None)
        default = _Point(x=0, y=0)

        result = await service.get_typed("missing", _Point, default=default)

        assert result is default


class TestCacheServiceGetTypedCoercionFailure:
    @pytest.mark.asyncio
    async def test_returns_default_when_coercion_fails(self) -> None:
        # A string value cannot construct a _Point via _Point("bad")
        service = _make_service("not-a-point-dict")

        result = await service.get_typed("pt", _Point, default=None)

        assert result is None
