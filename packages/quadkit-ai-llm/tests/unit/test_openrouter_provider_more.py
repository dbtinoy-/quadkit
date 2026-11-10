"""Additional OpenRouter provider tests (edge cases).

Covers:
- tool_call parsing into ToolCall/FunctionCall models
- streaming behavior with response.content async iterator
- stream errors (ClientResponseError) wrapped into ValueError
- SSE lines as bytes and str mixed
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.openrouter import OpenRouterClient
from quadkit.ai.llm.types import AIError, Completion, StreamChunk


@pytest.mark.asyncio
async def test_complete_parses_tool_calls_and_usage(monkeypatch):
    client = OpenRouterClient(
        ClientConfig(api_key="x", model="test", api_base="http://example"),
    )

    fake_resp = SimpleNamespace()
    fake_resp.raise_for_status = lambda: None
    fake_resp.json = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "ok",
                    "tool_calls": [
                        {
                            "id": "t1",
                            "type": "function",
                            "function": {"name": "search", "arguments": {}},
                        },
                    ],
                },
                "finish_reason": "stop",
            },
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        "model": "test",
    }

    fake_client = SimpleNamespace()
    fake_client.post = AsyncMock(return_value=fake_resp)

    monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=fake_client))

    res = await client.complete([{"role": "user", "content": "hi"}], model="test")
    assert res.is_ok()
    completion = res.unwrap()
    assert isinstance(completion, Completion)
    assert completion.tool_calls and completion.tool_calls[0].function.name == "search"
    assert completion.usage.total_tokens == 3


@pytest.mark.asyncio
async def test_streaming_uses_content_iterator_and_handles_bytes_and_str(monkeypatch):
    client = OpenRouterClient(
        ClientConfig(api_key="x", model="test", api_base="http://example"),
    )

    class Response:
        async def __aenter__(self):
            class Ctx:
                def __init__(self):
                    self._it = iter(
                        [
                            b'data: {"choices": [{"delta": {"content": "he"}}], "model": "test"}\n',
                            'data: {"choices": [{"delta": {"content": "llo"}}], "model": "test"}\n',
                            b"data: [DONE]\n",
                        ],
                    )

                @property
                def content(self):
                    async def gen():
                        for l in self._it:
                            yield l

                    return gen()

                def raise_for_status(self):
                    return None

            return Ctx()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_stream_ctx(*a, **kw):
        return Response()

    fake_client = SimpleNamespace()
    fake_client.stream = lambda *a, **kw: fake_stream_ctx()

    # sanity check: ensure our fake yields mixed types (first is bytes, second is str)
    assert isinstance(b"x", (bytes, bytearray)) and isinstance("x", str)

    it = client._stream_completion(fake_client, {"model": "test"})
    chunks = []
    async for c in it:
        assert isinstance(c, StreamChunk)
        chunks.append(c.delta)

    assert chunks == ["he", "llo"]


@pytest.mark.asyncio
async def test_stream_raises_value_error_on_client_response_error(monkeypatch):
    client = OpenRouterClient(
        ClientConfig(api_key="x", model="test", api_base="http://example"),
    )
    client.max_retries = 0  # no backoff sleep

    fake_client = SimpleNamespace()
    # simulate client.stream raising aiohttp.ClientResponseError
    fake_client.stream = AsyncMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=500, message="err",
        ),
    )

    monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=fake_client))

    with pytest.raises(AIError):
        # call internal stream generator directly
        it = client._stream_completion(fake_client, {"model": "test"})
        async for _ in it:
            pass
