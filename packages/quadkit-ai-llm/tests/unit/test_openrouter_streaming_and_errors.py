"""Tests for OpenRouter streaming behavior and error handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.openrouter import OpenRouterClient
from quadkit.ai.llm.types import AIError, ChatMessage, StreamChunk


class DummyStream:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        class Ctx:
            def __init__(self, lines):
                self._it = iter(lines)

            async def __aiter__(self):
                for l in self._it:
                    yield l

            # For compatibility with some usage patterns
            @property
            def content(self):
                async def gen():
                    for l in self._it:
                        yield l

                return gen()

        return Ctx(self._lines)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


@pytest.mark.asyncio
async def test_streaming_yields_chunks():
    client = OpenRouterClient(
        ClientConfig(api_key="x", model="test", api_base="http://example"),
    )

    # Simulate Server-Sent Events lines (bytes)
    # Two data lines and a DONE
    lines = [
        b'data: {"choices": [{"delta": {"content": "he"}}], "model": "test"}\n',
        b'data: {"choices": [{"delta": {"content": "llo"}}], "model": "test"}\n',
        b"data: [DONE]\n",
    ]

    fake_client = MagicMock()
    fake_client.stream = AsyncMock(return_value=DummyStream(lines))

    with patch.object(client, "_get_client", AsyncMock(return_value=fake_client)):
        it = client._stream_completion(fake_client, {"model": "test"})
        chunks = []
        async for c in it:
            assert isinstance(c, StreamChunk)
            chunks.append(c.delta)

        assert "he" in chunks[0]
        assert "llo" in chunks[1]


@pytest.mark.asyncio
async def test_streaming_skips_malformed_lines_and_supports_str_lines():
    client = OpenRouterClient(
        ClientConfig(api_key="x", model="test", api_base="http://example"),
    )

    # Malformed line should be skipped, then valid line, then DONE
    lines = [
        b"data: not-a-json\n",
        b'data: {"choices": [{"delta": {"content": "ok"}}], "model": "test"}\n',
        b"data: [DONE]\n",
    ]

    fake_client = MagicMock()
    fake_client.stream = AsyncMock(return_value=DummyStream(lines))

    with patch.object(client, "_get_client", AsyncMock(return_value=fake_client)):
        it = client._stream_completion(fake_client, {"model": "test"})
        chunks = []
        async for c in it:
            chunks.append(c.delta)

        assert chunks == ["ok"]

    # Now simulate string lines instead of bytes
    str_lines = [
        'data: {"choices": [{"delta": {"content": "sok"}}], "model": "test"}\n',
        "data: [DONE]\n",
    ]

    fake_client2 = MagicMock()
    fake_client2.stream = AsyncMock(return_value=DummyStream(str_lines))

    with patch.object(client, "_get_client", AsyncMock(return_value=fake_client2)):
        it = client._stream_completion(fake_client2, {"model": "test"})
        chunks = []
        async for c in it:
            chunks.append(c.delta)

        assert chunks == ["sok"]


@pytest.mark.asyncio
async def test_api_failure_raises_value_error():
    client = OpenRouterClient(
        ClientConfig(api_key="x", model="test", api_base="http://example"),
    )
    client.max_retries = 0  # no backoff sleep — error is non-retryable in this path

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=500, message="err",
        ),
    )

    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=fake_response)

    with patch.object(client, "_get_client", AsyncMock(return_value=fake_client)):
        with pytest.raises(AIError):
            await client.complete([ChatMessage(role="user", content="hello")])
