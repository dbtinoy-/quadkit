import asyncio

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.openrouter import OpenRouterClient, StreamChunk


class FakeResp:
    def __init__(self, data):
        self._data = data
        self.json = data

    def raise_for_status(self):
        return None


class FakeClientSyncPost:
    async def post(self, path, json=None):
        return FakeResp(json or {})


class AsyncCtx:
    def __init__(self, iterator):
        self.iterator = iterator

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeStreamResponse(AsyncCtx):
    def __init__(self, lines):
        super().__init__(None)

        async def gen():
            for l in lines:
                await asyncio.sleep(0)
                yield l

        # Provide both content (bytes iterator) and aiter_lines (str iterator)
        self.content = gen()
        self.aiter_lines = gen


class FakeClientStream:
    def __init__(self, lines, return_coroutine=False):
        self._lines = lines
        self._return_coroutine = return_coroutine

    def stream(self, *args, **kwargs):
        ctx = FakeStreamResponse(self._lines)
        if self._return_coroutine:

            async def coro():
                await asyncio.sleep(0)
                return ctx

            return coro()
        return ctx


@pytest.mark.asyncio
async def test_complete_sync_parses_choice_and_usage():
    c = OpenRouterClient(ClientConfig(api_key="x", model="mymodel"))

    fake = FakeClientSyncPost()

    data = {
        "choices": [
            {
                "message": {"content": "hello", "role": "assistant"},
                "finish_reason": "stop",
            },
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        "model": "mymodel",
    }

    resp = FakeResp(data)

    class P:
        async def post(self, path, json=None):
            return resp

    res = await c._complete(P(), {})
    assert res.content == "hello"
    assert res.usage.total_tokens == 3
    assert res.finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_completion_yields_chunks_bytes_and_str():
    c = OpenRouterClient(ClientConfig(api_key="x", model="mymodel"))

    # SSE lines include bytes and strings
    data1 = b'data: {"choices": [{"delta": {"content": "hi"}, "finish_reason": null}], "model": "mymodel" }\n'
    data2 = (
        'data: {"choices": [{"delta": {"content": " there"}}], "model": "mymodel" }\n'
    )
    done = b"data: [DONE]\n"

    fake_client = FakeClientStream([data1, data2, done])

    chunks = []
    async for chunk in c._stream_completion(fake_client, {}):
        chunks.append(chunk)

    assert isinstance(chunks[0], StreamChunk)
    assert "hi" in chunks[0].delta
    assert "there" in chunks[1].delta


@pytest.mark.asyncio
async def test_stream_completion_handles_coroutine_stream_ctx():
    c = OpenRouterClient(ClientConfig(api_key="x", model="mymodel"))

    # Test stream() returning a coroutine that resolves to context manager
    line = b'data: {"choices": [{"delta": {"content": "x"}}], "model": "mymodel" }\n'
    done = b"data: [DONE]\n"
    fake_client = FakeClientStream([line, done], return_coroutine=True)

    chunks = []
    async for chunk in c._stream_completion(fake_client, {}):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0].delta.strip() == "x"


@pytest.mark.asyncio
async def test_embeddings_returns_sorted_embeddings():
    c = OpenRouterClient(ClientConfig(api_key="x", model="mymodel"))

    class Client:
        async def post(self, path, json=None):
            return FakeResp(
                {
                    "data": [
                        {"index": 1, "embedding": [3.0, 4.0]},
                        {"index": 0, "embedding": [1.0, 2.0]},
                    ],
                },
            )

    # Monkeypatch _get_client to return our Client
    async def _get_client():
        return Client()

    c._get_client = _get_client
    out = await c.embeddings(["a", "b"], model="mymodel")
    assert out == [[1.0, 2.0], [3.0, 4.0]]
