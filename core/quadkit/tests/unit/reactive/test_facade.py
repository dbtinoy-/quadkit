"""Tests for the top-level quadkit facade."""

from __future__ import annotations

from typing import Any

import quadkit


def test_facade_exposes_reactive_core() -> None:
    assert hasattr(quadkit, "EventStream")
    assert hasattr(quadkit, "Subject")


async def test_facade_streams_work_end_to_end() -> None:
    async def gen() -> Any:
        for i in range(4):
            yield i

    stream = quadkit.Stream(gen()).pipe(quadkit.ops.map(lambda x: x + 1))
    assert [item async for item in stream] == [1, 2, 3, 4]