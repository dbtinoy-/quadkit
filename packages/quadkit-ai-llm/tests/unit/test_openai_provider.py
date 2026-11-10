"""Unit tests for the OpenAI provider using a fake `openai` module."""

import sys
from types import SimpleNamespace

from quadkit.validation import SecretStr
import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.openai import OpenAIClient
from quadkit.ai.llm.types import ChatMessage, Role, StreamChunk


class FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        async def _gen():
            for c in self._chunks:
                yield c

        return _gen()


class FakeChoiceMsg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message=None, finish_reason=None, delta=None):
        self.message = message
        self.finish_reason = finish_reason
        self.delta = delta


class FakeResponse:
    def __init__(self, choices, model="m", usage=None, **kwargs):
        self.choices = choices
        self.model = model
        self.usage = usage
        self.id = kwargs.get("id", "rid")
        self.created = kwargs.get("created", 1)
        self.system_fingerprint = kwargs.get("system_fingerprint", None)


@pytest.mark.asyncio
async def test_complete_success(monkeypatch):
    # Create fake openai.AsyncOpenAI
    class AsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace()

            # non-streaming create
            async def create(**params):
                choice = FakeChoice(
                    message=FakeChoiceMsg(content="hello"), finish_reason="stop",
                )
                return FakeResponse(
                    [choice],
                    model=params.get("model", "m"),
                    usage=SimpleNamespace(
                        prompt_tokens=1, completion_tokens=2, total_tokens=3,
                    ),
                )

            self.chat.completions = SimpleNamespace(create=create)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=AsyncOpenAI))

    config = ClientConfig(provider="openai", model="test-model", api_key=SecretStr("x"))
    client = OpenAIClient(config)

    res = await client.complete([ChatMessage(role=Role.USER, content="hi")])
    assert res.is_ok()
    completion = res.unwrap()
    assert completion.content == "hello"
    assert completion.model == "test-model"


@pytest.mark.asyncio
async def test_stream_chat_yields_chunks(monkeypatch):
    # Fake AsyncOpenAI with streaming returning async iterator
    class AsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace()

            async def create(**params):
                # return an async iterator
                chunks = [
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content="a"), finish_reason=None,
                            ),
                        ],
                        model="m",
                        finish_reason=None,
                    ),
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content="b"), finish_reason=None,
                            ),
                        ],
                        model="m",
                        finish_reason=None,
                    ),
                ]

                return FakeStream(chunks)

            self.chat.completions = SimpleNamespace(create=create)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=AsyncOpenAI))

    config = ClientConfig(provider="openai", model="test-model", api_key=SecretStr("x"))
    client = OpenAIClient(config)

    chunks = []
    # stream_chat() is not async anymore
    stream = client.stream_chat([ChatMessage(role=Role.USER, content="hi")])
    
    async for c in stream:
        assert isinstance(c, StreamChunk)
        chunks.append(c.delta)

    assert chunks == ["a", "b"]


@pytest.mark.asyncio
async def test_chat_parses_tool_calls_and_error_mapping(monkeypatch):
    class AsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace()

            async def create(**params):
                # Return normal response with tool_calls
                tc = SimpleNamespace(
                    id="1", function=SimpleNamespace(name="f", arguments={"x": 1}),
                )
                msg = SimpleNamespace(content="", tool_calls=[tc])
                choice = FakeChoice(message=msg, finish_reason="stop")
                return FakeResponse([choice], model=params.get("model", "m"))

            self.chat.completions = SimpleNamespace(create=create)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=AsyncOpenAI))

    config = ClientConfig(provider="openai", model="test-model", api_key=SecretStr("x"))
    client = OpenAIClient(config)

    res = await client.chat([ChatMessage(role=Role.USER, content="call")])
    assert res.is_ok()
    completion = res.unwrap()
    assert completion.tool_calls is not None
    assert completion.tool_calls[0].id == "1"

    # Error mapping: simulate auth error
    class AuthAI:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace()

            async def create(**params):
                raise Exception("Authentication failed: invalid key")

            self.chat.completions = SimpleNamespace(create=create)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=AuthAI))
    client2 = OpenAIClient(config)

    with pytest.raises(Exception):
        await client2.complete([ChatMessage(role=Role.USER, content="hi")])
