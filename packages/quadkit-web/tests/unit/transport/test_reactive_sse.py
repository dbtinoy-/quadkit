"""Tests for SSE bridging over reactive streams."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from quadkit.reactive import Stream
from quadkit.web.transport.reactive import sse_from_stream


@pytest.mark.asyncio
async def test_sse_from_stream_serializes_frames() -> None:
    async def gen() -> Any:
        yield {"value": 1}
        yield {"value": 2}

    response = sse_from_stream(
        Stream(gen()),
        serializer=lambda item: str(item["value"]),
    )
    body = "".join([chunk async for chunk in response.body_iterator])
    assert body == "data: 1\n\ndata: 2\n\n"


@pytest.mark.asyncio
async def test_sse_keepalive_on_silence() -> None:
    async def gen() -> Any:
        yield {"value": 1}
        await asyncio.sleep(0.1)
        yield {"value": 2}

    response = sse_from_stream(
        Stream(gen()),
        serializer=lambda item: str(item["value"]),
        keepalive=0.03,
    )
    body = "".join([chunk async for chunk in response.body_iterator])
    assert "data: 1" in body
    assert ": keepalive" in body
    assert "data: 2" in body
