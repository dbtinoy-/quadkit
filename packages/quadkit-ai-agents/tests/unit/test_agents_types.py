"""Tests for AI agents types."""

import pytest
from datetime import datetime, timezone

from quadkit.ai.agents.types import (
    AgentResponse,
    ReasoningStep,
    ToolExecutionRecord,
)


class TestToolExecutionRecord:
    """Tests for ToolCall dataclass."""

    def test_tool_call_defaults(self) -> None:
        """Test ToolExecutionRecord default values."""
        call = ToolExecutionRecord(tool_name="test_tool")
        assert call.tool_name == "test_tool"
        assert call.arguments == {}
        assert call.result is None
        assert call.error is None
        assert call.duration_ms == 0.0

    def test_tool_call_with_arguments(self) -> None:
        """Test ToolExecutionRecord with arguments."""
        call = ToolExecutionRecord(tool_name="get_weather", arguments={"city": "NYC"})
        assert call.tool_name == "get_weather"
        assert call.arguments == {"city": "NYC"}

    def test_tool_call_succeeded_property(self) -> None:
        """Test succeeded property."""
        success_call = ToolExecutionRecord(tool_name="test", result={"ok": True})
        assert success_call.succeeded is True

        fail_call = ToolExecutionRecord(tool_name="test", error="Something went wrong")
        assert fail_call.succeeded is False

    def test_tool_call_with_error(self) -> None:
        """Test ToolExecutionRecord with error."""
        call = ToolExecutionRecord(tool_name="test", error="Error message")
        assert call.error == "Error message"
        assert call.succeeded is False


class TestReasoningStep:
    """Tests for ReasoningStep dataclass."""

    def test_reasoning_step_defaults(self) -> None:
        """Test ReasoningStep default values."""
        step = ReasoningStep(step_number=1)
        assert step.step_number == 1
        assert step.thought == ""
        assert step.action is None
        assert step.tool_call is None
        assert step.observation is None

    def test_reasoning_step_with_thought(self) -> None:
        """Test ReasoningStep with thought."""
        step = ReasoningStep(
            step_number=1,
            thought="I should check the weather",
        )
        assert step.thought == "I should check the weather"

    def test_reasoning_step_with_tool_call(self) -> None:
        """Test ReasoningStep with tool call."""
        tool_call = ToolExecutionRecord(tool_name="get_weather", arguments={"city": "NYC"})
        step = ReasoningStep(
            step_number=1,
            action="get_weather",
            tool_call=tool_call,
            observation="It's sunny",
        )
        assert step.action == "get_weather"
        assert step.tool_call == tool_call
        assert step.observation == "It's sunny"


class TestAgentResponse:
    """Tests for AgentResponse type."""

    def test_agent_response_import(self) -> None:
        """Test AgentResponse can be imported."""
        assert AgentResponse is not None
