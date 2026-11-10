"""Tests for LLM types - type aliases, dataclasses, and enums."""

import pytest
from datetime import datetime, timezone

from quadkit.ai.llm import types as llm_types
from quadkit.contracts.ai.llm import Role
from quadkit.contracts.ai.thinking import ThinkingResult


class TestRole:
    def test_system(self) -> None:
        assert Role.SYSTEM == "system"

    def test_user(self) -> None:
        assert Role.USER == "user"

    def test_assistant(self) -> None:
        assert Role.ASSISTANT == "assistant"

    def test_tool(self) -> None:
        assert Role.TOOL == "tool"

    def test_function(self) -> None:
        assert Role.FUNCTION == "function"

    def test_is_str_enum(self) -> None:
        assert isinstance(Role.SYSTEM, str)

    def test_all_members_are_str(self) -> None:
        members = list(Role)
        assert set(m.value for m in members) == {"system", "user", "assistant", "tool", "function"}


class TestChatMessage:
    def test_create_minimal(self) -> None:
        msg = llm_types.ChatMessage(role=Role.USER, content="Hello")
        assert msg.role == Role.USER
        assert msg.content == "Hello"

    def test_create_with_name(self) -> None:
        msg = llm_types.ChatMessage(role=Role.USER, content="Hello", name="user1")
        assert msg.name == "user1"

    def test_create_with_tool_call_id(self) -> None:
        msg = llm_types.ChatMessage(
            role=Role.TOOL, content="Result", tool_call_id="call_123"
        )
        assert msg.tool_call_id == "call_123"

    def test_create_with_thinking_blocks(self) -> None:
        blocks = [{"type": "thinking", "thinking": "reasoning...", "signature": "sig123"}]
        msg = llm_types.ChatMessage(
            role=Role.ASSISTANT, content="Answer", thinking_blocks=blocks
        )
        assert msg.thinking_blocks == blocks


class TestCompletion:
    def test_create_minimal(self) -> None:
        completion = llm_types.Completion(content="Hello", model="gpt-4")
        assert completion.content == "Hello"
        assert completion.model == "gpt-4"

    def test_create_with_finish_reason(self) -> None:
        completion = llm_types.Completion(
            content="Hello", model="gpt-4", finish_reason="stop"
        )
        assert completion.finish_reason == "stop"

    def test_create_with_role(self) -> None:
        completion = llm_types.Completion(
            content="Hello", model="gpt-4", role=Role.ASSISTANT
        )
        assert completion.role == Role.ASSISTANT

    def test_create_with_tool_calls(self) -> None:
        tool_calls = [
            llm_types.ToolCall(
                id="call_123", type="function", function=llm_types.FunctionCall(
                    name="get_weather", arguments={"city": "NYC"}
                )
            )
        ]
        completion = llm_types.Completion(
            content="", model="gpt-4", tool_calls=tool_calls
        )
        assert completion.tool_calls == tool_calls

    def test_create_with_usage(self) -> None:
        usage = llm_types.TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        completion = llm_types.Completion(
            content="Hello", model="gpt-4", usage=usage
        )
        assert completion.usage == usage
        assert completion.usage.prompt_tokens == 10
        assert completion.usage.completion_tokens == 20
        assert completion.usage.total_tokens == 30

    def test_create_with_thinking(self) -> None:
        thinking = ThinkingResult(content=" reasoning...", signature="sig123", tokens=50)
        completion = llm_types.Completion(
            content="Answer", model="gpt-4", thinking=thinking
        )
        assert completion.thinking == thinking

    def test_create_with_metadata(self) -> None:
        completion = llm_types.Completion(
            content="Hello", model="gpt-4", metadata={"key": "value"}
        )
        assert completion.metadata == {"key": "value"}

    def test_default_timestamp(self) -> None:
        before = datetime.now(timezone.utc)
        completion = llm_types.Completion(content="Hello", model="gpt-4")
        after = datetime.now(timezone.utc)
        assert before <= completion.timestamp <= after


class TestStreamChunk:
    def test_create_minimal(self) -> None:
        chunk = llm_types.StreamChunk(delta="Hello", model="gpt-4")
        assert chunk.delta == "Hello"
        assert chunk.model == "gpt-4"

    def test_content_alias(self) -> None:
        chunk = llm_types.StreamChunk(content="Hello", model="gpt-4")
        assert chunk.delta == "Hello"
        assert chunk.content == "Hello"

    def test_delta_and_content_match(self) -> None:
        chunk = llm_types.StreamChunk(delta="Hello", content="Hello", model="gpt-4")
        assert chunk.delta == "Hello"

    def test_delta_content_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="delta and content must match"):
            llm_types.StreamChunk(delta="Hello", content="Different", model="gpt-4")

    def test_finish_reason(self) -> None:
        chunk = llm_types.StreamChunk(delta="Hello", model="gpt-4", finish_reason="stop")
        assert chunk.finish_reason == "stop"

    def test_role(self) -> None:
        chunk = llm_types.StreamChunk(delta="Hello", model="gpt-4", role=Role.ASSISTANT)
        assert chunk.role == Role.ASSISTANT

    def test_index_default(self) -> None:
        chunk = llm_types.StreamChunk(delta="Hello", model="gpt-4")
        assert chunk.index == 0

    def test_custom_index(self) -> None:
        chunk = llm_types.StreamChunk(delta="Hello", model="gpt-4", index=5)
        assert chunk.index == 5

    def test_default_tokens_used(self) -> None:
        chunk = llm_types.StreamChunk(delta="Hello", model="gpt-4")
        assert chunk.tokens_used == 0

    def test_default_metadata(self) -> None:
        chunk = llm_types.StreamChunk(delta="Hello", model="gpt-4")
        assert chunk.metadata == {}

    def test_thinking_delta(self) -> None:
        chunk = llm_types.StreamChunk(
            delta="", model="gpt-4", thinking_delta="reasoning...", is_thinking=True
        )
        assert chunk.thinking_delta == "reasoning..."
        assert chunk.is_thinking is True


class TestFunctionCall:
    def test_create_minimal(self) -> None:
        fc = llm_types.FunctionCall(name="get_weather")
        assert fc.name == "get_weather"
        assert fc.arguments == {}

    def test_create_with_dict_arguments(self) -> None:
        fc = llm_types.FunctionCall(name="get_weather", arguments={"city": "NYC"})
        assert fc.arguments == {"city": "NYC"}

    def test_create_with_str_arguments(self) -> None:
        fc = llm_types.FunctionCall(name="get_weather", arguments='{"city": "NYC"}')
        assert fc.arguments == '{"city": "NYC"}'


class TestToolCall:
    def test_create_minimal(self) -> None:
        tc = llm_types.ToolCall(id="call_123")
        assert tc.id == "call_123"
        assert tc.type == "function"
        assert tc.function is None

    def test_create_with_function(self) -> None:
        fc = llm_types.FunctionCall(name="get_weather", arguments={"city": "NYC"})
        tc = llm_types.ToolCall(id="call_123", function=fc)
        assert tc.function == fc


class TestTokenUsage:
    def test_create(self) -> None:
        usage = llm_types.TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


class TestThinkingResult:
    def test_create_minimal(self) -> None:
        result = ThinkingResult(content=" reasoning...")
        assert result.content == " reasoning..."
        assert result.signature is None
        assert result.tokens is None

    def test_create_full(self) -> None:
        result = ThinkingResult(content=" reasoning...", signature="sig123", tokens=100)
        assert result.content == " reasoning..."
        assert result.signature == "sig123"
        assert result.tokens == 100


class TestExceptionAliases:
    def test_ai_error_is_llm_error(self) -> None:
        assert llm_types.AIError is llm_types.LLMError

    def test_llm_error_base(self) -> None:
        assert issubclass(llm_types.LLMError, Exception)

    def test_invalid_request_error(self) -> None:
        assert issubclass(llm_types.InvalidRequestError, llm_types.LLMError)

    def test_llm_authentication_error(self) -> None:
        assert issubclass(llm_types.LLMAuthenticationError, llm_types.LLMError)

    def test_llm_rate_limit_error(self) -> None:
        assert issubclass(llm_types.LLMRateLimitError, llm_types.LLMError)


class TestExports:
    def test_all_exports(self) -> None:
        expected = {
            "AIError",
            "ChatMessage",
            "Completion",
            "FunctionCall",
            "InvalidRequestError",
            "LLMAuthenticationError",
            "LLMError",
            "LLMRateLimitError",
            "Role",
            "StreamChunk",
            "ThinkingResult",
            "TokenUsage",
            "ToolCall",
        }
        assert set(llm_types.__all__) == expected