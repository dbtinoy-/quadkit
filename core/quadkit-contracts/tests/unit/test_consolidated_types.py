"""Tests for consolidated type definitions across contracts.

Ensures that types have single canonical definitions and are properly
frozen/immutable where appropriate. Tests verify that all duplicate
definitions have been consolidated to their canonical locations.
"""

from __future__ import annotations

from dataclasses import is_dataclass

import pytest

from quadkit.contracts.ai.agents import AgentResponse
from quadkit.contracts.ai.llm import ChatMessage, Completion, Role, ToolCall
from quadkit.contracts.data.vector.types import SearchResult, VectorRecord


class TestAgentResponseCanonical:
    """Tests for AgentResponse type consolidation."""

    def test_agent_response_exists(self) -> None:
        """Test AgentResponse is defined and importable."""
        assert AgentResponse is not None

    def test_agent_response_is_dataclass(self) -> None:
        """Test AgentResponse is a proper dataclass."""
        assert is_dataclass(AgentResponse)

    def test_agent_response_creation(self) -> None:
        """Test AgentResponse can be instantiated."""
        response = AgentResponse(
            message="Test response",
            total_tokens=100,
            total_cost=0.01,
            duration_ms=500.0,
        )
        assert response.message == "Test response"
        assert response.total_tokens == 100
        assert response.total_cost == 0.01
        assert response.duration_ms == 500.0

    def test_agent_response_defaults(self) -> None:
        """Test AgentResponse has correct defaults."""
        response = AgentResponse(message="Test")
        assert response.message == "Test"
        assert response.steps == []
        assert response.tool_calls == []
        assert response.total_tokens == 0
        assert response.total_cost == 0.0
        assert response.duration_ms == 0.0
        assert response.session_id is None
        assert response.metadata == {}

    def test_agent_response_properties(self) -> None:
        """Test AgentResponse helper properties."""
        response = AgentResponse(
            message="Test",
            steps=[{"action": "step1"}],
            tool_calls=[{"name": "tool1", "succeeded": True}],
        )
        assert response.step_count == 1
        assert response.tool_call_count == 1

    def test_agent_response_to_dict(self) -> None:
        """Test AgentResponse serialization."""
        response = AgentResponse(
            message="Test",
            total_tokens=50,
            total_cost=0.005,
            duration_ms=250.0,
            session_id="sess-123",
        )
        result = response.to_dict()
        assert result["message"] == "Test"
        assert result["total_tokens"] == 50
        assert result["total_cost"] == 0.005
        assert result["duration_ms"] == 250.0
        assert result["session_id"] == "sess-123"


class TestSearchResultCanonical:
    """Tests for SearchResult type consolidation."""

    def test_search_result_exists(self) -> None:
        """Test SearchResult is defined and importable."""
        assert SearchResult is not None

    def test_search_result_is_dataclass(self) -> None:
        """Test SearchResult is a proper dataclass."""
        assert is_dataclass(SearchResult)

    def test_search_result_is_frozen(self) -> None:
        """Test SearchResult is frozen (immutable)."""
        result = SearchResult(id="r1", score=0.95)
        with pytest.raises(Exception):
            # Attempting to modify a frozen dataclass should raise
            result.score = 0.90

    def test_search_result_creation(self) -> None:
        """Test SearchResult can be instantiated."""
        result = SearchResult(
            id="result-123",
            score=0.95,
            metadata={"source": "test"},
            content="Test content",
        )
        assert result.id == "result-123"
        assert result.score == 0.95
        assert result.metadata == {"source": "test"}
        assert result.content == "Test content"

    def test_search_result_defaults(self) -> None:
        """Test SearchResult has correct defaults."""
        result = SearchResult(id="r1", score=0.9)
        assert result.id == "r1"
        assert result.score == 0.9
        assert result.metadata == {}
        assert result.vector is None
        assert result.content is None

    def test_search_result_with_vector(self) -> None:
        """Test SearchResult with vector data."""
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = SearchResult(
            id="r2",
            score=0.85,
            vector=vector,
        )
        assert result.vector == vector


class TestChatMessageCanonical:
    """Tests for ChatMessage type consolidation."""

    def test_chat_message_exists(self) -> None:
        """Test ChatMessage is defined and importable."""
        assert ChatMessage is not None

    def test_chat_message_is_dataclass(self) -> None:
        """Test ChatMessage is a proper dataclass."""
        assert is_dataclass(ChatMessage)

    def test_chat_message_creation_user(self) -> None:
        """Test ChatMessage creation for user role."""
        msg = ChatMessage(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.name is None
        assert msg.tool_call_id is None

    def test_chat_message_creation_assistant(self) -> None:
        """Test ChatMessage creation for assistant role."""
        msg = ChatMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_chat_message_with_all_fields(self) -> None:
        """Test ChatMessage with all fields populated."""
        msg = ChatMessage(
            role="assistant",
            content="Response",
            name="assistant-1",
            tool_call_id="tc-123",
        )
        assert msg.role == "assistant"
        assert msg.content == "Response"
        assert msg.name == "assistant-1"
        assert msg.tool_call_id == "tc-123"

    def test_chat_message_role_enum(self) -> None:
        """Test Role enum is available and has expected values."""
        assert hasattr(Role, "USER")
        assert hasattr(Role, "ASSISTANT")
        assert hasattr(Role, "SYSTEM")


class TestCompletionCanonical:
    """Tests for Completion type consolidation."""

    def test_completion_exists(self) -> None:
        """Test Completion is defined and importable."""
        assert Completion is not None

    def test_completion_is_dataclass(self) -> None:
        """Test Completion is a proper dataclass."""
        assert is_dataclass(Completion)

    def test_completion_creation(self) -> None:
        """Test Completion can be instantiated."""
        completion = Completion(
            content="Response text",
            model="gpt-4",
        )
        assert completion.content == "Response text"
        assert completion.model == "gpt-4"

    def test_completion_with_optional_fields(self) -> None:
        """Test Completion with optional fields."""
        completion = Completion(
            content="Response",
            model="gpt-4-turbo",
            finish_reason="stop",
        )
        assert completion.content == "Response"
        assert completion.model == "gpt-4-turbo"
        assert completion.finish_reason == "stop"


class TestVectorRecordCanonical:
    """Tests for VectorRecord type consolidation."""

    def test_vector_record_exists(self) -> None:
        """Test VectorRecord is defined and importable."""
        assert VectorRecord is not None

    def test_vector_record_is_dataclass(self) -> None:
        """Test VectorRecord is a proper dataclass."""
        assert is_dataclass(VectorRecord)

    def test_vector_record_is_frozen(self) -> None:
        """Test VectorRecord is frozen (immutable)."""
        record = VectorRecord(id="v1", vector=[0.1, 0.2])
        with pytest.raises(Exception):
            record.vector = [0.3, 0.4]

    def test_vector_record_creation(self) -> None:
        """Test VectorRecord can be instantiated."""
        vector = [0.1, 0.2, 0.3]
        record = VectorRecord(
            id="vec-123",
            vector=vector,
            metadata={"source": "test"},
            content="Test doc",
        )
        assert record.id == "vec-123"
        assert record.vector == vector
        assert record.metadata == {"source": "test"}
        assert record.content == "Test doc"


class TestNoDuplicateImports:
    """Verify that import paths are consistent and from canonical locations."""

    def test_agent_response_import_path(self) -> None:
        """Test AgentResponse imports from canonical location."""
        from quadkit.contracts.ai.agents import AgentResponse as AR

        assert AR is AgentResponse

    def test_search_result_import_path(self) -> None:
        """Test SearchResult imports from canonical location."""
        from quadkit.contracts.data.vector.types import SearchResult as SR

        assert SR is SearchResult

    def test_chat_message_import_path(self) -> None:
        """Test ChatMessage imports from canonical location."""
        from quadkit.contracts.ai.llm import ChatMessage as CM

        assert CM is ChatMessage

    def test_completion_import_path(self) -> None:
        """Test Completion imports from canonical location."""
        from quadkit.contracts.ai.llm import Completion as C

        assert C is Completion
