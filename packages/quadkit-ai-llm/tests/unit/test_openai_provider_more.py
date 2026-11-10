"""Additional OpenAI provider tests (non-stream and stream)."""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

from quadkit.validation import SecretStr
import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.openai import OpenAIClient
from quadkit.ai.llm.types import ChatMessage, Role, StreamChunk


@pytest.mark.asyncio
async def test_openai_complete_and_chat(monkeypatch):
    # Create fake openai package
    class FakeChoiceMessage:
        def __init__(self, content="hello"):
            self.content = content
            self.tool_calls = None

    class FakeChoice:
        def __init__(self):
            self.message = FakeChoiceMessage()
            self.finish_reason = "stop"

    class FakeResponse:
        def __init__(self):
            self.choices = [FakeChoice()]
            self.model = "gpt-4"
            self.usage = SimpleNamespace(
                prompt_tokens=1, completion_tokens=2, total_tokens=3,
            )
            self.id = "rid"
            self.created = 123
            self.system_fingerprint = "fp"

    class FakeAsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace()

            async def create(**params):
                return FakeResponse()

            self.chat.completions = SimpleNamespace(
                create=AsyncMock(side_effect=create),
            )

    sys.modules["openai"] = SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)

    config = ClientConfig(provider="openai", model="gpt-4", api_key=SecretStr("x"))
    client = OpenAIClient(config)

    res = await client.complete([ChatMessage(role=Role.USER, content="hi")])
    assert res.is_ok()
    completion = res.unwrap()
    assert completion.content == "hello"
    assert completion.model == "gpt-4"


@pytest.mark.asyncio
async def test_openai_stream_chat(monkeypatch):
    class Chunk:
        async def __aiter__(self):
            for t in ["a", "b"]:
                # create a choice-like object expected by the provider
                delta = SimpleNamespace(content=t)
                # The streaming API yields chunk objects; chunk.choices[0].delta is expected
                chunk_obj = SimpleNamespace(
                    choices=[SimpleNamespace(delta=delta, finish_reason=None)],
                    model="gpt-4",
                    finish_reason=None,
                )
                yield chunk_obj

    class FakeAsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace()

            async def create(**params):
                # streaming returns an async iterable
                return Chunk()

            self.chat.completions = SimpleNamespace(
                create=AsyncMock(side_effect=create),
            )

    sys.modules["openai"] = SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)

    config = ClientConfig(provider="openai", model="gpt-4", api_key=SecretStr("x"))
    client = OpenAIClient(config)

    chunks = []
    stream = client.stream_chat([ChatMessage(role=Role.USER, content="hi")])
    async for c in stream:
        assert isinstance(c, StreamChunk)
        chunks.append(c.delta)

    assert chunks == ["a", "b"]
