"""Public-surface export regression tests for quadkit.contracts.ai."""
from __future__ import annotations

from quadkit.contracts.ai import (
    ChatMessage,
    FunctionCall,
    MessageContent,
    ToolCall,
    ToolDefinition,
)
from quadkit.contracts.ai.llm import (
    ChatMessage as LLMChatMessage,
    FunctionCall as LLMFunctionCall,
    ToolCall as LLMToolCall,
)
from quadkit.contracts.ai.multimodal import (
    MessageContent as MultimodalMessageContent,
)
from quadkit.contracts.ai.agents import (
    ToolDefinition as AgentsToolDefinition,
)


def test_shared_chat_message_identity() -> None:
    """ChatMessage re-exports the canonical llm definition."""
    assert ChatMessage is LLMChatMessage


def test_function_call_identity() -> None:
    """FunctionCall re-exports the canonical llm definition."""
    assert FunctionCall is LLMFunctionCall


def test_tool_call_identity() -> None:
    """ToolCall re-exports the canonical llm definition."""
    assert ToolCall is LLMToolCall


def test_message_content_identity() -> None:
    """MessageContent re-exports the canonical multimodal definition."""
    assert MessageContent is MultimodalMessageContent


def test_tool_definition_identity() -> None:
    """ToolDefinition re-exports the canonical agents definition."""
    assert ToolDefinition is AgentsToolDefinition


def test_function_call_accepts_arguments() -> None:
    """FunctionCall carries a name and JSON-encoded arguments."""
    call = FunctionCall(name="add", arguments='{"a": 1, "b": 2}')
    assert call.name == "add"
    assert call.arguments == '{"a": 1, "b": 2}'


def test_tool_call_accepts_identity_and_function() -> None:
    """ToolCall carries an id and an embedded FunctionCall."""
    call = ToolCall(
        id="call_1",
        function=FunctionCall(name="add", arguments='{"a": 1}'),
    )
    assert call.id == "call_1"
    assert call.function.name == "add"