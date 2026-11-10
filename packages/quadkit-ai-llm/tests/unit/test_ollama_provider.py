"""Tests for Ollama provider."""

from unittest.mock import AsyncMock, MagicMock

from quadkit.validation import SecretStr
import pytest

pytest.importorskip("ollama")

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.ollama import OllamaClient
from quadkit.ai.llm.types import ChatMessage, FunctionCall, Role, StreamChunk, ToolCall
from quadkit.contracts.ai.agents import ToolDefinition


@pytest.mark.asyncio
async def test_tool_calling_complete(monkeypatch):
    """Native tool definitions are converted and tool calls parsed."""
    config = ClientConfig(provider="ollama", model="m")
    client = OllamaClient(config)

    tool = ToolDefinition(
        name="search_knowledge",
        description="Search the knowledge base.",
        parameters={
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    )

    captured = {}

    async def fake_chat(**kwargs):
        captured["params"] = kwargs
        return {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_knowledge",
                            "arguments": {"topic": "providers"},
                        }
                    }
                ],
            },
            "model": "m",
            "prompt_eval_count": 10,
            "eval_count": 3,
        }

    client.client = MagicMock()
    client.client.chat = fake_chat

    res = await client.complete(
        [ChatMessage(role=Role.USER, content="List providers")],
        tools=[tool],
    )
    assert res.is_ok()
    completion = res.unwrap()

    # tools were sent to Ollama in wire format (not raw ToolDefinition)
    sent_tools = captured["params"]["tools"]
    assert sent_tools == [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "description": "Search the knowledge base.",
                "parameters": {
                    "type": "object",
                    "properties": {"topic": {"type": "string"}},
                    "required": ["topic"],
                },
            },
        }
    ]

    # tool calls parsed back into framework ToolCalls
    assert completion.tool_calls is not None
    assert len(completion.tool_calls) == 1
    tc = completion.tool_calls[0]
    assert tc.function is not None
    assert tc.function.name == "search_knowledge"
    assert tc.function.arguments == {"topic": "providers"}


@pytest.mark.asyncio
async def test_tool_result_round_trip_is_serialized():
    """Assistant tool calls are re-serialized back to Ollama wire format."""
    config = ClientConfig(provider="ollama", model="m")
    client = OllamaClient(config)

    messages = [
        ChatMessage(role=Role.USER, content="List providers"),
        ChatMessage(
            role=Role.ASSISTANT,
            content="",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    type="function",
                    function=FunctionCall(name="search_knowledge", arguments={"topic": "providers"}),
                )
            ],
        ),
        ChatMessage(role=Role.TOOL, content="ollama, openai, anthropic"),
    ]

    serialized = await client._serialize_messages_for_ollama(messages)

    assert serialized[0] == {"role": "user", "content": "List providers"}
    assert serialized[1]["tool_calls"] == [
        {"function": {"name": "search_knowledge", "arguments": {"topic": "providers"}}}
    ]
    assert serialized[2] == {"role": "tool", "content": "ollama, openai, anthropic"}


@pytest.mark.asyncio
async def test_complete_and_streaming(monkeypatch):
    config = ClientConfig(provider="ollama", model="m", api_key=SecretStr("x"))
    client = OllamaClient(config)

    # fake chat response
    fake_chat = AsyncMock(
        return_value={
            "message": {"content": "hello"},
            "model": "m",
            "prompt_eval_count": 1,
            "eval_count": 2,
        },
    )
    client.client = MagicMock()
    client.client.chat = fake_chat

    res = await client.complete([ChatMessage(role=Role.USER, content="hi")])
    assert res.is_ok()
    completion = res.unwrap()
    assert completion.content == "hello"

    # streaming: client.chat returns an async iterable when awaited
    async def stream_gen():
        for chunk in [
            {"message": {"content": "h"}, "model": "m"},
            {"message": {"content": "i"}, "model": "m", "done": True},
        ]:
            yield chunk

    client.client.chat = AsyncMock(return_value=stream_gen())

    chunks = []
    stream = client.stream_chat(
        [ChatMessage(role=Role.USER, content="hi")], model="m",
    )
    async for c in stream:
        assert isinstance(c, StreamChunk)
        chunks.append(c.delta)

    assert chunks == ["h", "i"]
