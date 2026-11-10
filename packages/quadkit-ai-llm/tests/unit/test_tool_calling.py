"""Unit tests for native tool calling across LLM providers."""

import sys
from types import SimpleNamespace

import pytest

from quadkit.ai.llm.clients import (
    _tools_utils,
)
from quadkit.ai.llm.clients.anthropic import AnthropicClient
from quadkit.ai.llm.clients.gemini_helpers import messages_to_gemini
from quadkit.ai.llm.clients.openai import OpenAIClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.types import (
    ChatMessage,
    FunctionCall,
    Role,
    ToolCall,
)
from quadkit.contracts.ai.agents import ToolDefinition
from quadkit.validation import SecretStr

TOOL = ToolDefinition(
    name="search_knowledge",
    description="Search the knowledge base.",
    parameters={
        "type": "object",
        "properties": {"topic": {"type": "string"}},
        "required": ["topic"],
    },
)


def _tool_message() -> ChatMessage:
    return ChatMessage(
        role=Role.TOOL,
        content="ollama, openai, anthropic",
        tool_call_id="call-1",
    )


def _assistant_with_calls() -> ChatMessage:
    return ChatMessage(
        role=Role.ASSISTANT,
        content="",
        tool_calls=[
            ToolCall(
                id="call-1",
                type="function",
                function=FunctionCall(
                    name="search_knowledge", arguments={"topic": "providers"}
                ),
            )
        ],
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def test_tool_to_openai_format_from_tool_definition():
    wire = _tools_utils.tool_to_openai_format(TOOL)
    assert wire == {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the knowledge base.",
            "parameters": TOOL.parameters,
        },
    }


def test_tool_to_openai_format_from_schema_class():
    class Weather:
        __tool_schema__ = {
            "name": "get_weather",
            "description": "Current weather.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
            },
        }

    wire = _tools_utils.tool_to_openai_format(Weather)
    assert wire["function"]["name"] == "get_weather"
    assert wire["function"]["parameters"]["properties"]["city"]["type"] == "string"


def test_tool_to_openai_format_from_dict():
    raw = {
        "type": "function",
        "function": {
            "name": "raw_tool",
            "description": "d",
            "parameters": {"type": "object"},
        },
    }
    assert _tools_utils.tool_to_openai_format(raw) == raw


def test_serialize_message_for_openai_round_trip():
    assert _tools_utils.serialize_message_for_openai(
        ChatMessage(role=Role.USER, content="hi")
    ) == {"role": "user", "content": "hi"}

    assistant = _tools_utils.serialize_message_for_openai(_assistant_with_calls())
    assert assistant["role"] == "assistant"
    assert assistant["content"] is None
    assert assistant["tool_calls"] == [
        {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "arguments": '{"topic":"providers"}',
            },
        }
    ]

    tool = _tools_utils.serialize_message_for_openai(_tool_message())
    assert tool == {
        "role": "tool",
        "content": "ollama, openai, anthropic",
        "tool_call_id": "call-1",
    }


def test_parse_openai_tool_calls_sdk_objects_and_dicts():
    sdk = [
        SimpleNamespace(
            id="1",
            type="function",
            function=SimpleNamespace(name="f", arguments='{"x": 1}'),
        )
    ]
    parsed = _tools_utils.parse_openai_tool_calls(sdk)
    assert parsed is not None
    assert parsed[0].function.name == "f"
    assert parsed[0].function.arguments == '{"x": 1}'
    assert _tools_utils.parse_json_arguments(parsed[0].function.arguments) == {"x": 1}

    as_dict = [
        {
            "id": "2",
            "type": "function",
            "function": {"name": "g", "arguments": {"y": 2}},
        }
    ]
    parsed2 = _tools_utils.parse_openai_tool_calls(as_dict)
    assert parsed2[0].id == "2"
    assert parsed2[0].function.arguments == {"y": 2}


# ---------------------------------------------------------------------------
# OpenAI (also covers openai_compatible / azure_openai)
# ---------------------------------------------------------------------------


class FakeChoiceMsg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message=None, finish_reason=None):
        self.message = message
        self.finish_reason = finish_reason


class FakeResponse:
    def __init__(self, choices, model="m", usage=None, **kwargs):
        self.choices = choices
        self.model = model
        self.usage = usage or SimpleNamespace(
            prompt_tokens=1, completion_tokens=2, total_tokens=3
        )
        self.id = kwargs.get("id", "rid")
        self.created = kwargs.get("created", 1)
        self.system_fingerprint = kwargs.get("system_fingerprint")


def _fake_async_openai(monkeypatch, captured, response):
    class AsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace()

            async def create(**params):
                captured["params"] = params
                return response(params)

            self.chat.completions = SimpleNamespace(create=create)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=AsyncOpenAI))


@pytest.mark.asyncio
async def test_openai_complete_with_tools(monkeypatch):
    captured = {}

    def response(params):
        tc = SimpleNamespace(
            id="1",
            type="function",
            function=SimpleNamespace(
                name="search_knowledge", arguments='{"topic": "providers"}'
            ),
        )
        return FakeResponse(
            [FakeChoice(message=FakeChoiceMsg(content="", tool_calls=[tc]))],
            model=params.get("model", "m"),
        )

    _fake_async_openai(monkeypatch, captured, response)
    config = ClientConfig(provider="openai", model="m", api_key=SecretStr("x"))
    client = OpenAIClient(config)

    messages = [
        ChatMessage(role=Role.USER, content="List providers"),
        _assistant_with_calls(),
        _tool_message(),
    ]
    res = await client.complete(messages, tools=[TOOL])
    assert res.is_ok()
    completion = res.unwrap()

    # wire format: tools converted, tool role has tool_call_id, assistant tool_calls re-emitted
    params = captured["params"]
    assert params["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "description": "Search the knowledge base.",
                "parameters": TOOL.parameters,
            },
        }
    ]
    wire_msgs = params["messages"]
    assert wire_msgs[1]["tool_calls"][0]["function"]["name"] == "search_knowledge"
    assert wire_msgs[2]["tool_call_id"] == "call-1"

    # tool calls parsed back into framework ToolCalls
    assert completion.tool_calls is not None
    assert completion.tool_calls[0].function.name == "search_knowledge"
    assert _tools_utils.parse_json_arguments(
        completion.tool_calls[0].function.arguments
    ) == {"topic": "providers"}


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


def _fake_anthropic(monkeypatch, captured):
    class AsyncAnthropic:
        def __init__(self, *args, **kwargs):
            self.messages = SimpleNamespace()

            async def create(**params):
                captured["params"] = params
                return SimpleNamespace(
                    id="m-1",
                    type="message",
                    role="assistant",
                    model=params.get("model", "m"),
                    content=[
                        SimpleNamespace(
                            type="tool_use",
                            id="call-1",
                            name="search_knowledge",
                            input={"topic": "providers"},
                        )
                    ],
                    stop_reason="tool_use",
                    usage=SimpleNamespace(
                        input_tokens=1,
                        output_tokens=2,
                        cache_creation_input_tokens=0,
                        cache_read_input_tokens=0,
                    ),
                )

            self.messages.create = create

    monkeypatch.setitem(
        sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=AsyncAnthropic)
    )


@pytest.mark.asyncio
async def test_anthropic_complete_with_tools(monkeypatch):
    captured = {}
    _fake_anthropic(monkeypatch, captured)

    config = ClientConfig(provider="anthropic", model="m", api_key=SecretStr("x"))
    client = AnthropicClient(config)

    messages = [
        ChatMessage(role=Role.USER, content="List providers"),
        _assistant_with_calls(),
        _tool_message(),
    ]
    res = await client.complete(messages, tools=[TOOL])
    assert res.is_ok()
    completion = res.unwrap()

    params = captured["params"]
    assert params["tools"] == [
        {
            "name": "search_knowledge",
            "description": "Search the knowledge base.",
            "input_schema": TOOL.parameters,
        }
    ]
    # tool result round-trips as a user turn with tool_result block
    tool_turn = params["messages"][2]
    assert tool_turn["role"] == "user"
    assert tool_turn["content"][0]["type"] == "tool_result"
    assert tool_turn["content"][0]["tool_use_id"] == "call-1"
    # assistant tool_calls re-emitted as tool_use blocks
    assert any(
        b["type"] == "tool_use" and b["name"] == "search_knowledge"
        for b in params["messages"][1]["content"]
    )

    assert completion.tool_calls is not None
    assert completion.tool_calls[0].function.name == "search_knowledge"
    assert _tools_utils.parse_json_arguments(
        completion.tool_calls[0].function.arguments
    ) == {"topic": "providers"}


# ---------------------------------------------------------------------------
# Gemini helpers (used by gemini + vertex_ai)
# ---------------------------------------------------------------------------


def test_gemini_messages_round_trip_tool_calls():
    messages = [
        ChatMessage(role=Role.USER, content="List providers"),
        _assistant_with_calls(),
        # Gemini keys function responses by the function name (parse sets
        # ToolCall.id = name), so the tool message must carry that id.
        ChatMessage(
            role=Role.TOOL,
            content="ollama, openai, anthropic",
            tool_call_id="search_knowledge",
        ),
    ]
    parts = messages_to_gemini(messages)

    assert parts[0]["parts"] == [{"text": "List providers"}]
    # assistant: functionCall parts, no empty text part
    assert parts[1]["role"] == "model"
    assert any("functionCall" in p for p in parts[1]["parts"])
    assert not any("text" in p for p in parts[1]["parts"])
    # tool result: functionResponse part
    assert parts[2]["role"] == "user"
    assert parts[2]["parts"][0]["functionResponse"]["name"] == "search_knowledge"
    assert (
        parts[2]["parts"][0]["functionResponse"]["response"]["content"]
        == "ollama, openai, anthropic"
    )


def test_gemini_tool_to_function_declaration():
    from quadkit.ai.llm.clients.gemini_helpers import tool_to_gemini_function

    wire = tool_to_gemini_function(TOOL)
    assert wire == {
        "name": "search_knowledge",
        "description": "Search the knowledge base.",
        "parameters": TOOL.parameters,
    }


# ---------------------------------------------------------------------------
# Cohere payload builder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cohere_payload_with_tools():
    from unittest.mock import AsyncMock, MagicMock

    from quadkit.ai.llm.clients._cohere_mappers import build_cohere_payload

    client = MagicMock()
    client.post = AsyncMock()

    _, payload, model = build_cohere_payload(
        client=client,
        messages=[
            ChatMessage(role=Role.USER, content="List providers"),
            _assistant_with_calls(),
            _tool_message(),
        ],
        stream=False,
        kwargs={"tools": [TOOL]},
        default_model="command-r",
        logger=MagicMock(),
    )

    assert model == "command-r"
    # the pending user text stays as the top-level message (existing convention)
    assert payload["message"] == "List providers"
    assert payload["tools"] == [
        {
            "name": "search_knowledge",
            "description": "Search the knowledge base.",
            "parameter_definitions": {
                "topic": {"description": "", "type": "string", "required": True}
            },
        }
    ]
    # assistant tool calls re-emitted in Cohere wire format
    assistant_entry = payload["chat_history"][0]
    assert assistant_entry["role"] == "CHATBOT"
    assert assistant_entry["tool_calls"] == [
        {"name": "search_knowledge", "parameters": {"topic": "providers"}}
    ]
    # tool result becomes a USER turn carrying tool_results
    tool_turn = payload["chat_history"][1]
    assert tool_turn["role"] == "USER"
    assert tool_turn["tool_results"][0]["call"]["name"] == "call-1"
