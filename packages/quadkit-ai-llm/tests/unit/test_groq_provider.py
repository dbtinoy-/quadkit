"""Tests for the Groq provider."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.groq import GroqClient
from quadkit.ai.llm.types import Completion, StreamChunk


@pytest.mark.asyncio
async def test_complete_non_streaming():
    client = GroqClient(ClientConfig(provider="groq", model="m", api_key="x"))

    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json = {
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }

    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=fake_resp)

    client._client = fake_client

    res = await client.complete(messages=[{"role": "user", "content": "hi"}], model="m")
    assert res.is_ok()
    completion = res.unwrap()
    assert isinstance(completion, Completion)
    assert completion.content == "ok"
    assert completion.usage.total_tokens == 3


@pytest.mark.asyncio
async def test_stream_completion_yields_chunks():
    client = GroqClient(ClientConfig(provider="groq", model="m", api_key="x"))

    class Ctx:
        async def __aenter__(self):
            class Inner:
                def __init__(self):
                    self._it = iter(
                        [
                            'data: {"choices": [{"delta": {"content": "he"}}], "model": "m"}',
                            'data: {"choices": [{"delta": {"content": "llo"}}], "model": "m"}',
                            "data: [DONE]",
                        ],
                    )

                def raise_for_status(self):
                    return None

                async def aiter_lines(self):
                    for l in self._it:
                        # simulate async pacing
                        await asyncio.sleep(0)
                        yield l

            return Inner()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_client = MagicMock()
    fake_client.stream = MagicMock(return_value=Ctx())

    it = client._stream_completion(fake_client, {"model": "m"})

    chunks = []
    async for c in it:
        assert isinstance(c, StreamChunk)
        chunks.append(c.delta)

    assert "he" in chunks[0]
    assert "llo" in chunks[1]


@pytest.mark.asyncio
async def test_list_models(monkeypatch):
    client = GroqClient(ClientConfig(provider="groq", model="m", api_key="x"))

    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json = {"data": [{"id": "m1"}]}

    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)

    client._client = fake_client

    models = await client.list_models()
    assert models == [{"id": "m1"}]
