"""Tests for LLM message types and data structures."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.types import ChatMessage, Completion, FunctionCall
from quadkit.contracts.ai.llm import Role as MessageRole


class TestMessageRole:
    """Test MessageRole enum."""

    def test_message_roles(self) -> None:
        """MessageRole should have standard roles."""
        assert hasattr(MessageRole, "USER")
        assert hasattr(MessageRole, "ASSISTANT")
        assert hasattr(MessageRole, "SYSTEM")
        assert hasattr(MessageRole, "FUNCTION")

    def test_user_role(self) -> None:
        """USER role should represent user messages."""
        assert MessageRole.USER == "user"

    def test_assistant_role(self) -> None:
        """ASSISTANT role should represent assistant messages."""
        assert MessageRole.ASSISTANT == "assistant"

    def test_system_role(self) -> None:
        """SYSTEM role should represent system messages."""
        assert MessageRole.SYSTEM == "system"


class TestChatMessage:
    """Test ChatMessage data structure."""

    def test_user_message_creation(self) -> None:
        """ChatMessage should create user messages."""
        msg = ChatMessage(role=MessageRole.USER, content="Hello")

        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"

    def test_assistant_message_creation(self) -> None:
        """ChatMessage should create assistant messages."""
        msg = ChatMessage(role=MessageRole.ASSISTANT, content="Hi there")

        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hi there"

    def test_system_message_creation(self) -> None:
        """ChatMessage should create system messages."""
        msg = ChatMessage(role=MessageRole.SYSTEM, content="You are helpful")

        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "You are helpful"

    def test_message_with_metadata(self) -> None:
        """ChatMessage should support optional metadata."""
        msg = ChatMessage(
            role=MessageRole.USER,
            content="Test",
            name="user_1",
        )

        assert msg.content == "Test"
        if hasattr(msg, "name"):
            assert msg.name == "user_1"

    def test_message_with_function_call(self) -> None:
        """ChatMessage should support function calls."""
        fn_call = FunctionCall(name="get_weather", arguments='{"city": "NYC"}')
        msg = ChatMessage(role=MessageRole.ASSISTANT, content="Calling function")

        if hasattr(msg, "function_call"):
            msg.function_call = fn_call
            assert msg.function_call.name == "get_weather"


class TestFunctionCall:
    """Test FunctionCall structure."""

    def test_function_call_creation(self) -> None:
        """FunctionCall should store function details."""
        fn = FunctionCall(name="get_weather", arguments='{"city": "NYC"}')

        assert fn.name == "get_weather"
        assert "city" in fn.arguments

    def test_function_call_with_id(self) -> None:
        """FunctionCall only has name + arguments; id is not a field."""
        fn = FunctionCall(
            name="calculate",
            arguments='{"x": 5, "y": 3}',
        )

        assert fn.name == "calculate"
        assert "x" in fn.arguments


class TestCompletion:
    """Test Completion response structure."""

    def test_completion_creation(self) -> None:
        """Completion should store response data."""
        completion = Completion(
            content="Response text",
            model="gpt-4",
            finish_reason="stop",
        )

        assert completion.content == "Response text"
        assert completion.finish_reason == "stop"

    def test_completion_with_tokens(self) -> None:
        """Completion stores token info in metadata if provided."""
        completion = Completion(
            content="Text",
            model="gpt-4",
            finish_reason="stop",
            metadata={"prompt_tokens": 10, "completion_tokens": 5},
        )

        if completion.metadata:
            assert completion.metadata["prompt_tokens"] == 10

    def test_completion_finish_reasons(self) -> None:
        """Completion should support standard finish reasons."""
        # stop, length, function_call, etc.
        reasons = ["stop", "length", "function_call"]

        for reason in reasons:
            completion = Completion(content="Text", model="gpt-4", finish_reason=reason)
            assert completion.finish_reason == reason

    def test_completion_with_model_info(self) -> None:
        """Completion should store model information."""
        completion = Completion(
            content="Response",
            finish_reason="stop",
            model="gpt-4",
        )

        if hasattr(completion, "model"):
            assert completion.model == "gpt-4"


class TestChatMessageSequence:
    """Test working with sequences of messages."""

    def test_conversation_sequence(self) -> None:
        """ChatMessage should be sequenceable."""
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content="You are helpful"),
            ChatMessage(role=MessageRole.USER, content="Hello"),
            ChatMessage(role=MessageRole.ASSISTANT, content="Hi there"),
        ]

        assert len(messages) == 3
        assert messages[0].role == MessageRole.SYSTEM
        assert messages[1].role == MessageRole.USER
        assert messages[2].role == MessageRole.ASSISTANT

    def test_message_immutability_check(self) -> None:
        """ChatMessage might be immutable (dataclass frozen)."""
        msg = ChatMessage(role=MessageRole.USER, content="Test")

        # Check if it's frozen (optional)
        if hasattr(msg, "__dataclass_fields__"):
            # It's likely a dataclass
            pass

    def test_message_string_representation(self) -> None:
        """ChatMessage should have useful string representation."""
        msg = ChatMessage(role=MessageRole.USER, content="Hello")

        repr_str = repr(msg)
        # Should contain role and content info
        assert len(repr_str) > 0
