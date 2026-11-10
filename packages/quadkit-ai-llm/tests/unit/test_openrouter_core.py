from unittest.mock import AsyncMock, MagicMock

import pytest

try:
    from quadkit.ai.llm.config import ClientConfig
    from quadkit.ai.llm.clients.openrouter import OpenRouterClient
    from quadkit.ai.llm.types import StreamChunk
except ImportError:
    # Some test environments load package-level config that may raise Pydantic errors
    pytest.skip(
        "OpenRouterProvider tests skipped due to import errors in package init",
        allow_module_level=True,
    )


@pytest.mark.asyncio
async def test_complete_sync_parses_tool_calls_and_usage(monkeypatch):
    client = OpenRouterClient(ClientConfig(api_key="x", model="m1"))

    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json = {
        "choices": [
            {
                "message": {
                    "content": "ok",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "1",
                            "type": "function",
                            "function": {"name": "f", "arguments": {}},
                        },
                    ],
                },
            },
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        "model": "m1",
    }

    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=fake_resp)

    async def get_client():
        return fake_client

    monkeypatch.setattr(client, "_get_client", get_client)

    res = await client.complete([{"role": "user", "content": "hi"}])
    assert res.is_ok()
    completion = res.unwrap()
    assert completion.content == "ok"
    assert completion.usage.total_tokens == 3
    assert completion.tool_calls is not None


@pytest.mark.asyncio
async def test_stream_completion_handles_bytes_and_coroutine_stream(monkeypatch):
    client = OpenRouterClient(ClientConfig(api_key="x", model="m1"))

    class Ctx:
        async def __aenter__(self):
            class Inner:
                def __init__(self):
                    self._it = iter(
                        [
                            b'data: {"choices": [{"delta": {"content": "he"}}], "model": "m1"}',
                            b"data: [DONE]",
                        ],
                    )

                async def aiter_lines(self):
                    for l in self._it:
                        yield l

                @property
                def content(self):
                    async def gen():
                        for l in self._it:
                            yield l

                    return gen()

            return Inner()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def stream_coro(*args, **kwargs):
        return Ctx()

    fake_client = MagicMock()
    fake_client.stream = MagicMock(side_effect=lambda *a, **kw: stream_coro())

    it = client._stream_completion(fake_client, {"model": "m1"})
    chunks = []
    async for c in it:
        assert isinstance(c, StreamChunk)
        chunks.append(c.delta)

    assert any("he" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_embeddings_returns_sorted(monkeypatch):
    client = OpenRouterClient(ClientConfig(api_key="x", model="m1"))

    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json = {
        "data": [
            {"index": 2, "embedding": [0.2]},
            {"index": 0, "embedding": [0.0]},
            {"index": 1, "embedding": [0.1]},
        ],
    }

    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=fake_resp)

    async def get_client():
        return fake_client

    monkeypatch.setattr(client, "_get_client", get_client)

    res = await client.embeddings(["a", "b", "c"])
    assert res == [[0.0], [0.1], [0.2]]
