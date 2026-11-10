"""Unit tests for Anthropic provider."""

from types import SimpleNamespace

from quadkit.validation import SecretStr
import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.anthropic import AnthropicClient
from quadkit.ai.llm.types import ChatMessage, Role, StreamChunk


@pytest.mark.asyncio
async def test_complete_success_and_generate_prompt(monkeypatch):
    class AsyncAnthropic:
        def __init__(self, *args, **kwargs):
            self.messages = SimpleNamespace()

            async def create(**params):
                # Simulate response object
                usage = SimpleNamespace(input_tokens=1, output_tokens=2)
                content_item = SimpleNamespace(text="hello")
                response = SimpleNamespace(
                    content=[content_item],
                    model=params.get("model", "m"),
                    stop_reason="stop",
                    usage=usage,
                    id="rid",
                    type="response",
                )
                return response

            self.messages.create = create

    monkeypatch.setitem(
        __import__("sys").modules,
        "anthropic",
        SimpleNamespace(AsyncAnthropic=AsyncAnthropic),
    )

    config = ClientConfig(provider="anthropic", model="claude", api_key=SecretStr("x"))
    client = AnthropicClient(config)

    res = await client.complete([ChatMessage(role=Role.USER, content="hi")])
    assert res.is_ok()
    completion = res.unwrap()
    assert completion.content == "hello"
    assert completion.model == "claude"


@pytest.mark.asyncio
async def test_stream_chat_yields_chunks(monkeypatch):
    class AsyncAnthropic:
        def __init__(self, *args, **kwargs):
            self.messages = SimpleNamespace()

            class StreamCtx:
                async def __aenter__(self):
                    class Ctx:
                        def __init__(self):
                            self._it = iter(["a", "b"])

                        async def __aiter__(self):
                            for t in self._it:
                                yield t

                        @property
                        def text_stream(self):
                            return self.__aiter__()

                    return Ctx()

                async def __aexit__(self, exc_type, exc, tb):
                    return False

            async def stream(**params):
                return StreamCtx()

            self.messages.stream = stream

    monkeypatch.setitem(
        __import__("sys").modules,
        "anthropic",
        SimpleNamespace(AsyncAnthropic=AsyncAnthropic),
    )

    config = ClientConfig(provider="anthropic", model="claude", api_key=SecretStr("x"))
    client = AnthropicClient(config)

    chunks = []
    stream = client.stream_chat([ChatMessage(role=Role.USER, content="hi")])
    async for c in stream:
        assert isinstance(c, StreamChunk)
        chunks.append(c.delta)

    assert chunks == ["a", "b"]
