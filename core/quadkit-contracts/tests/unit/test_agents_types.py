"""Unit tests for quadkit.contracts.agents types."""

from __future__ import annotations

import pytest

from quadkit.contracts.ai import AgentResponse


class TestAgentResponse:
    """Tests for AgentResponse dataclass."""

    def test_create_minimal_response(self) -> None:
        """Verify minimal AgentResponse creation."""
        response = AgentResponse(message="Hello, world!")
        assert response.message == "Hello, world!"
        assert response.steps == []
        assert response.tool_calls == []
        assert response.total_tokens == 0
        assert response.total_cost == 0.0
        assert response.duration_ms == 0.0

    def test_create_full_response(self) -> None:
        """Verify AgentResponse with all fields."""
        response = AgentResponse(
            message="Task completed",
            steps=["step1", "step2"],
            tool_calls=["tool1", "tool2", "tool3"],
            total_tokens=1500,
            total_cost=0.05,
            duration_ms=2500.0,
            session_id="session-123",
            metadata={"model": "gpt-4", "temperature": 0.7},
        )
        assert response.message == "Task completed"
        assert response.steps == ["step1", "step2"]
        assert response.tool_calls == ["tool1", "tool2", "tool3"]
        assert response.total_tokens == 1500
        assert response.total_cost == 0.05
        assert response.duration_ms == 2500.0
        assert response.session_id == "session-123"
        assert response.metadata == {"model": "gpt-4", "temperature": 0.7}

    def test_default_metadata_is_empty_dict(self) -> None:
        """Verify default metadata is empty dict."""
        response = AgentResponse(message="test")
        assert response.metadata == {}

    def test_tool_call_count_property(self) -> None:
        """Verify tool_call_count property."""
        response = AgentResponse(
            message="test",
            tool_calls=["tool1", "tool2", "tool3"],
        )
        assert response.tool_call_count == 3

    def test_tool_call_count_empty(self) -> None:
        """Verify tool_call_count when no tool calls."""
        response = AgentResponse(message="test")
        assert response.tool_call_count == 0

    def test_step_count_property(self) -> None:
        """Verify step_count property."""
        response = AgentResponse(
            message="test",
            steps=["step1", "step2", "step3"],
        )
        assert response.step_count == 3

    def test_step_count_empty(self) -> None:
        """Verify step_count when no steps."""
        response = AgentResponse(message="test")
        assert response.step_count == 0

    def test_session_id_can_be_none(self) -> None:
        """Verify session_id can be None."""
        response = AgentResponse(message="test", session_id=None)
        assert response.session_id is None

    def test_cost_is_float(self) -> None:
        """Verify total_cost is a float."""
        response = AgentResponse(message="test", total_cost=0.025)
        assert isinstance(response.total_cost, float)
        assert response.total_cost == 0.025

    def test_duration_is_float(self) -> None:
        """Verify duration_ms is a float."""
        response = AgentResponse(message="test", duration_ms=1000.5)
        assert isinstance(response.duration_ms, float)
        assert response.duration_ms == 1000.5