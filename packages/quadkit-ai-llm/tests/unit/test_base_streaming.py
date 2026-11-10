"""Tests for streaming behavior in ``AbstractLLMClient``."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.ai.llm.clients.base import AbstractLLMClient
from quadkit.ai.llm.exceptions import LLMError
from quadkit.ai.llm.types import ChatMessage, Completion, Role, StreamChunk
from quadkit.contracts.infra import AsyncStream
from quadkit.result import Ok


def _make_client() -> AbstractLLMClient:
    """Create a minimal streaming client under test."""
    from quadkit.ai.llm.config import ClientConfig

    config = MagicMock(spec=ClientConfig)
    config.provider = MagicMock()
    config.provider.value = "test"
    config.timeout = 0.01
    config.extra = {}

    class _ConcreteClient(AbstractLLMClient):
        async def _do_complete(self, messages, **kwargs):
            return Ok(Completion(content="ok", model="test-model"))

        async def _do_stream_chat(self, messages, **kwargs):
            async def _stream():
                yield StreamChunk(delta="hi")
                raise RuntimeError("STREAM_FAILURE_SECRET_SENTINEL")

            return Ok(_stream())

        async def _do_chat(self, messages, tools=None, **kwargs):
            return Ok(Completion(content="ok", model="test-model"))

        async def health_check(self, timeout=5.0):
            return MagicMock()

    return _ConcreteClient(config=config)


class TestBaseStreaming:
    """Tests for typed streaming results."""

    @pytest.mark.asyncio
    async def test_stream_chat_wraps_midstream_failures_in_async_stream(self) -> None:
        """Mid-stream failures should be surfaced through ``AsyncStream``."""
        client = _make_client()

        # stream_chat() is NOT async per spec — returns AsyncStream directly
        stream = client.stream_chat(
            [ChatMessage(role=Role.USER, content="hello")]
        )

        assert isinstance(stream, AsyncStream)

        collected = await stream.collect()

        assert collected.is_err()
        error = collected.unwrap_err()
        assert isinstance(error, LLMError)
        assert "STREAM_FAILURE_SECRET_SENTINEL" not in str(error)
        assert error.details == {"error_type": "RuntimeError"}

    @pytest.mark.asyncio
    async def test_stream_chat_returns_stream_immediately(self) -> None:
        """stream_chat() should return AsyncStream synchronously."""
        client = _make_client()

        # No await — method is not async
        stream = client.stream_chat(
            [ChatMessage(role=Role.USER, content="hello")]
        )

        # Should get stream object immediately
        assert isinstance(stream, AsyncStream)
        # Stream is lazy — consuming it triggers the async work
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
        assert len(chunks) >= 1
