"""Tests for typed async streams."""

from __future__ import annotations

import pytest

from quadkit.contracts.infra import AsyncStream


async def _failing_stream() -> object:
    yield "alpha"
    yield "beta"
    raise RuntimeError("stream exploded")


async def _number_stream() -> object:
    for value in range(6):
        yield value


class TestAsyncStream:
    """Tests for ``AsyncStream``."""

    @pytest.mark.asyncio
    async def test_collect_returns_err_for_midstream_failure(self) -> None:
        """Collect should capture a stream failure as ``Err``."""
        stream = AsyncStream(_failing_stream(), error_adapter=str)

        result = await stream.collect()

        assert result.is_err()
        assert result.unwrap_err() == "stream exploded"

    @pytest.mark.asyncio
    async def test_map_filter_take_transform_lazily(self) -> None:
        """Map, filter, and take should preserve lazy stream composition."""
        stream = (
            AsyncStream(_number_stream(), error_adapter=str)
            .filter(lambda value: value % 2 == 0)
            .map(lambda value: value * 10)
            .take(2)
        )

        result = await stream.collect()

        assert result.is_ok()
        assert result.unwrap() == [0, 20]
