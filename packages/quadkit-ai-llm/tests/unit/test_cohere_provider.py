"""Tests for Cohere provider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.clients.cohere import COHERE_MODELS, CohereClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.types import StreamChunk


def test_cohere_models_export_available():
    assert "command-r" in COHERE_MODELS


@pytest.mark.asyncio
async def test_complete_and_embeddings_success():
    client = CohereClient(ClientConfig(provider="cohere", model="command", api_key="x"))

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json = {
        "text": "hi",
        "meta": {"tokens": {"input_tokens": 1, "output_tokens": 2}},
    }

    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=fake_response)

    # Patch _get_client
    client._client = fake_client

    res = await client.complete(
        messages=[{"role": "user", "content": "hello"}],
        model="command",
    )
    assert res.is_ok()
    completion = res.unwrap()
    assert completion.content == "hi"
    assert completion.usage.total_tokens == 3

    # embeddings
    fake_emb = MagicMock()
    fake_emb.raise_for_status = MagicMock()
    fake_emb.json = {"embeddings": [[0.1, 0.2]]}
    fake_client.post = AsyncMock(return_value=fake_emb)

    embs = await client.embed(["hello"])
    assert embs == [[0.1, 0.2]]


@pytest.mark.asyncio
async def test_stream_completion_parses_events():
    client = CohereClient(ClientConfig(provider="cohere", model="command", api_key="x"))

    class DummyCtx:
        async def __aenter__(self):
            class Ctx:
                def __init__(self):
                    self._it = iter(
                        [
                            '{"event_type": "text-generation", "text": "he"}',
                            '{"event_type": "text-generation", "text": "llo"}',
                            '{"event_type": "stream-end", "finish_reason": "stop"}',
                        ],
                    )

                def raise_for_status(self):
                    return None

                async def aiter_lines(self):
                    for line in self._it:
                        yield line

            return Ctx()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_client = MagicMock()
    fake_client.stream = MagicMock(return_value=DummyCtx())

    client._client = fake_client

    stream = client.stream_chat(messages=[], model="command")
    chunks = []
    async for c in stream:
        assert isinstance(c, StreamChunk)
        chunks.append(c.delta)

    assert "he" in chunks[0]
    assert "llo" in chunks[1]
