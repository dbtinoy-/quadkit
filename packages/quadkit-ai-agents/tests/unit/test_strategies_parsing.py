"""Tests for strategy parsing utilities."""

from __future__ import annotations

import pytest

from quadkit.ai.agents.strategies.parsing import (
    build_chat_messages,
    build_chat_messages_from_dict,
    extract_final_answer,
    extract_thought,
    extract_tool_call,
)
from quadkit.contracts.ai.llm import ChatMessage, Role


class TestExtractThought:
    """Tests for extract_thought."""

    def test_extract_thought_from_text(self) -> None:
        text = "THOUGHT: I need to search for the answer\nACTION: search"
        result = extract_thought(text)
        assert result == "I need to search for the answer"

    def test_extract_thought_case_insensitive(self) -> None:
        text = "thought: thinking here\nACTION: done"
        result = extract_thought(text)
        assert result == "thinking here"

    def test_extract_thought_fallback_to_first_line(self) -> None:
        text = "No thought marker here\nSecond line"
        result = extract_thought(text)
        assert result == "No thought marker here"

    def test_extract_thought_short_fallback(self) -> None:
        text = "a" * 300
        result = extract_thought(text)
        assert len(result) <= 200


class TestExtractFinalAnswer:
    """Tests for extract_final_answer."""

    def test_extract_final_answer(self) -> None:
        text = "Some reasoning\nFINAL_ANSWER: The result is 42"
        result = extract_final_answer(text)
        assert result == "The result is 42"

    def test_extract_final_answer_case_insensitive(self) -> None:
        text = "final_answer: yes"
        result = extract_final_answer(text)
        assert result == "yes"

    def test_extract_final_answer_not_found(self) -> None:
        text = "No final answer here"
        result = extract_final_answer(text)
        assert result is None

    def test_extract_final_answer_empty(self) -> None:
        text = "FINAL_ANSWER:"
        result = extract_final_answer(text)
        assert result == ""


class TestExtractToolCall:
    """Tests for extract_tool_call."""

    def test_extract_action_and_input(self) -> None:
        text = "ACTION: search\nACTION_INPUT: {\"query\": \"hello\"}"
        action_name, action_input = extract_tool_call(text)
        assert action_name == "search"
        assert action_input == {"query": "hello"}

    def test_extract_action_only(self) -> None:
        text = "ACTION: search"
        action_name, action_input = extract_tool_call(text)
        assert action_name == "search"
        assert action_input == {}

    def test_extract_no_action(self) -> None:
        text = "Just some text"
        action_name, action_input = extract_tool_call(text)
        assert action_name is None
        assert action_input == {}

    def test_extract_malformed_json_fallback(self) -> None:
        text = "ACTION: search\nACTION_INPUT: {invalid json here {query: test}}"
        action_name, action_input = extract_tool_call(text)
        assert action_name == "search"

    def test_extract_valid_json_in_braces(self) -> None:
        text = 'ACTION_INPUT: some text {"key": "value"} more text'
        action_name, action_input = extract_tool_call(text)
        assert action_input == {"key": "value"}


class TestBuildChatMessages:
    """Tests for build_chat_messages."""

    def test_build_with_system_prompt(self) -> None:
        messages = build_chat_messages(
            "user message",
            [ChatMessage(role=Role.ASSISTANT, content="previous")],
            "system prompt",
        )
        assert len(messages) == 3
        assert messages[0].role == Role.SYSTEM
        assert messages[0].content == "system prompt"
        assert messages[1].role == Role.ASSISTANT
        assert messages[2].role == Role.USER
        assert messages[2].content == "user message"

    def test_build_without_system_prompt(self) -> None:
        messages = build_chat_messages(
            "user message",
            [],
            "",
        )
        assert len(messages) == 1
        assert messages[0].role == Role.USER
        assert messages[0].content == "user message"

    def test_build_with_empty_history(self) -> None:
        messages = build_chat_messages("hello", [], "system")
        assert len(messages) == 2


class TestBuildChatMessagesFromDict:
    """Tests for build_chat_messages_from_dict."""

    def test_build_from_dict_with_system(self) -> None:
        messages = build_chat_messages_from_dict(
            "hello",
            [{"role": "assistant", "content": "previous"}],
            "system prompt",
        )
        assert len(messages) == 3
        assert messages[0].role == Role.SYSTEM
        assert messages[1].role == Role.ASSISTANT
        assert messages[2].role == Role.USER

    def test_build_from_dict_fallback_to_user(self) -> None:
        messages = build_chat_messages_from_dict(
            "hello",
            [{"role": "invalid_role", "content": "data"}],
            "",
        )
        assert len(messages) == 2
        assert messages[0].role == Role.USER

    def test_build_from_dict_without_system(self) -> None:
        messages = build_chat_messages_from_dict("hello", [], "")
        assert len(messages) == 1
        assert messages[0].role == Role.USER
