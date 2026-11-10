"""Tests for Mock LLM clients."""

import pytest

from support.mock_clients import (
    MockLLMClient,
    MockLLMClientWithErrors,
    MockStreamingLLMClient,
)
from quadkit.ai.llm.types import AIError, StreamChunk


@pytest.mark.asyncio
async def test_mock_complete_and_usage():
    m = MockLLMClient(responses=["the answer is 42"], model="m-mock")
    res = await m.complete([{"role": "user", "content": "what"}])
    assert res.is_ok()
    completion = res.unwrap()
    assert completion.content == "the answer is 42"
    assert completion.model == "m-mock"
    assert completion.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_stream_chat_and_finish_reason():
    m = MockLLMClient(responses=["hi there"])

    chunks = []
    # stream_chat() is not async anymore
    stream = m.stream_chat([{"role": "user", "content": "say hi"}])
    async for c in stream:
        assert isinstance(c, StreamChunk)
        chunks.append(c.delta)

    assert "hi" in "".join(chunks)


@pytest.mark.asyncio
async def test_mock_with_errors_raises():
    m = MockLLMClientWithErrors(responses=["ok"], error_on_call=1, error_message="boom")
    res = await m.complete([{"role": "user", "content": "hi"}])
    assert res.is_err()
    assert isinstance(res.unwrap_err(), AIError)


@pytest.mark.asyncio
async def test_mock_streaming_variants():
    ms = MockStreamingLLMClient(responses=["hello world"], stream_by="char")
    collected = []
    # stream_chat() is not async anymore
    stream = ms.stream_chat([{"role": "user", "content": "x"}])
    async for c in stream:
        collected.append(c.delta)

    assert "".join(collected).replace(" ", "") == "helloworld"
