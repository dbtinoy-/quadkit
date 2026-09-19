"""Tests for transform operators."""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.reactive import EventStream, Stream, ops


async def gen() -> Any:
    for i in range(5):
        yield i


async def collect(stream: EventStream[Any]) -> list[Any]:
    return [item async for item in stream]


async def test_map_transforms_sync() -> None:
    assert await collect(Stream(gen()).pipe(ops.map(lambda x: x * 2))) == [0, 2, 4, 6, 8]


async def test_map_supports_async_transform() -> None:
    async def async_double(x: int) -> int:
        await asyncio.sleep(0.001)
        return x * 2

    assert await collect(Stream(gen()).pipe(ops.map(async_double))) == [0, 2, 4, 6, 8]


async def test_filter_keeps_matching_items() -> None:
    assert await collect(Stream(gen()).pipe(ops.filter(lambda x: x % 2 == 0))) == [0, 2, 4]


async def test_scan_accumulates_with_initial() -> None:
    assert await collect(Stream(gen()).pipe(ops.scan(lambda acc, x: acc + x, 0))) == [
        0,
        1,
        3,
        6,
        10,
    ]


async def test_distinct_emits_first_occurrence() -> None:
    async def dup_gen() -> Any:
        for x in [1, 1, 2, 3, 2, 3]:
            yield x

    assert await collect(Stream(dup_gen()).pipe(ops.distinct())) == [1, 2, 3]


async def test_distinct_with_key() -> None:
    async def pair_gen() -> Any:
        yield {"id": 1, "v": "a"}
        yield {"id": 1, "v": "b"}
        yield {"id": 2, "v": "c"}

    assert await collect(Stream(pair_gen()).pipe(ops.distinct(lambda d: d["id"]))) == [
        {"id": 1, "v": "a"},
        {"id": 2, "v": "c"},
    ]