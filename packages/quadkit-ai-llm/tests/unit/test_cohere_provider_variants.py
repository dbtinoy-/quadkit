from types import SimpleNamespace

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.cohere import CohereClient
from quadkit.ai.llm.types import StreamChunk


@pytest.mark.asyncio
async def test_stream_handles_coroutine_and_bytes_lines():
    client = CohereClient(ClientConfig(api_key="x"))

    class Response:
        async def __aenter__(self):
            class Ctx:
                def __init__(self):
                    self._it = iter(
                        [
                            b'{"event_type":"text-generation","text":"ab"}',
                            b'{"event_type":"stream-end","finish_reason":"stop"}',
                        ],
                    )

                def raise_for_status(self):
                    return None

                async def aiter_lines(self):
                    for l in self._it:
                        yield l

            return Ctx()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_stream_ctx(*a, **kw):
        return Response()

    fake_client = SimpleNamespace()
    fake_client.stream = lambda *a, **kw: fake_stream_ctx()

    it = client._stream_completion(fake_client, {"model": "command"})

    chunks = []
    async for c in it:
        assert isinstance(c, StreamChunk)
        chunks.append(c)

    assert any("ab" in c.delta for c in chunks)


@pytest.mark.asyncio
async def test_stream_handles_mixed_bytes_and_str_lines():
    client = CohereClient(ClientConfig(api_key="x"))

    class Response:
        async def __aenter__(self):
            class Ctx:
                def __init__(self):
                    self._it = iter(
                        [
                            '{"event_type":"text-generation","text":"x"}',
                            b'{"event_type":"text-generation","text":"y"}',
                            '{"event_type":"stream-end","finish_reason":"stop"}',
                        ],
                    )

                def raise_for_status(self):
                    return None

                async def aiter_lines(self):
                    for l in self._it:
                        yield l

            return Ctx()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_client = SimpleNamespace()
    fake_client.stream = lambda *a, **kw: Response()

    it = client._stream_completion(fake_client, {"model": "command"})

    contents = []
    async for c in it:
        contents.append(c.delta)

    assert "x" in contents
    assert "y" in contents
