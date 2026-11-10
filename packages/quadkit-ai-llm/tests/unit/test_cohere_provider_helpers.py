"""Extended Cohere provider tests using shared helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.cohere import CohereClient
from quadkit.ai.llm.types import StreamChunk, AIError

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from provider_helpers import make_fake_client


@pytest.mark.asyncio
async def test_stream_uses_content_iterator_and_mixed_bytes_and_str(monkeypatch):
    client = CohereClient(ClientConfig(api_key="x"))

    lines = [
        b'{"event_type":"text-generation","text":"ab"}',
        '{"event_type":"text-generation","text":"x"}',
        b'{"event_type":"stream-end","finish_reason":"stop"}',
    ]
    fake_client = make_fake_client(stream_lines=lines, use_content=True)

    monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=fake_client))

    it = client._stream_completion(fake_client, {"model": "command"})

    contents = []
    async for c in it:
        assert isinstance(c, StreamChunk)
        contents.append(c.delta)

    assert "ab" in contents
    assert "x" in contents


@pytest.mark.asyncio
async def test_stream_raises_ai_error_on_client_response_error(monkeypatch):
    client = CohereClient(ClientConfig(api_key="x"))

    fake_client = make_fake_client(
        stream_raises=aiohttp.ClientResponseError(
            request_info=SimpleNamespace(real_url=""), history=(), status=500, message="err",
        ),
    )

    monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=fake_client))

    with pytest.raises(AIError):
        it = client._stream_completion(fake_client, {"model": "command"})
        async for _ in it:
            pass
