"""Unit tests for AgentAsToolAdapter."""

from __future__ import annotations

import pytest

from quadkit.ai.agents.delegation.agent_tool import AgentAsToolAdapter
from quadkit.ai.agents.types import AgentResponse


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, name: str = "test_agent", system_prompt: str = "Test agent prompt"):
        self.name = name
        self.system_prompt = system_prompt


from quadkit.result import Err, Ok


class MockExecutor:
    """Mock executor for testing."""

    def __init__(self, response: str = "Agent response"):
        self.response = response
        self.run_calls = []

    async def run(self, agent, message: str, session_id: str | None = None, user_id: str | None = None):
        self.run_calls.append({
            "agent": agent,
            "message": message,
            "session_id": session_id,
            "user_id": user_id,
        })
        return Ok(AgentResponse(message=self.response))


class TestAgentAsToolAdapter:
    """Tests for AgentAsToolAdapter."""

    @pytest.mark.asyncio
    async def test_adapter_execute_calls_executor(self) -> None:
        """Test adapter delegates to executor when execute is called."""
        mock_executor = MockExecutor(response="Sub-agent result")
        mock_agent = MockAgent(name="billing")

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
        )

        result = await adapter.execute(message="Process payment")

        assert "Process payment" in [call["message"] for call in mock_executor.run_calls]
        assert "Sub-agent result" in result

    def test_adapter_generates_correct_schema(self) -> None:
        """Test adapter generates correct parameters schema."""
        mock_executor = MockExecutor()
        mock_agent = MockAgent(name="search")

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
        )

        schema = adapter.parameters_schema

        assert schema["type"] == "object"
        assert "message" in schema["properties"]
        assert schema["properties"]["message"]["type"] == "string"
        assert "message" in schema["required"]

    def test_adapter_name_format(self) -> None:
        """Test adapter name follows delegate_to_<agent_name> format."""
        mock_executor = MockExecutor()
        mock_agent = MockAgent(name="technical_support")

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
        )

        assert adapter.name == "delegate_to_technical_support"

    def test_adapter_description(self) -> None:
        """Test adapter description includes agent info."""
        mock_executor = MockExecutor()
        mock_agent = MockAgent(
            name="research",
            system_prompt="You are a research assistant that finds information.",
        )

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
        )

        assert "research" in adapter.description
        assert "research assistant" in adapter.description

    @pytest.mark.asyncio
    async def test_adapter_description_truncation(self) -> None:
        """Test adapter truncates long descriptions."""
        mock_executor = MockExecutor()
        long_prompt = "A" * 300
        mock_agent = MockAgent(name="long_agent", system_prompt=long_prompt)

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
        )

        assert len(adapter.description) <= 240

    @pytest.mark.asyncio
    async def test_adapter_handles_empty_message(self) -> None:
        """Test adapter handles empty message gracefully."""
        mock_executor = MockExecutor()
        mock_agent = MockAgent()

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
        )

        result = await adapter.execute(message="")
        assert "Error" in result or "No message" in result

    @pytest.mark.asyncio
    async def test_adapter_optional_session_user_ids(self) -> None:
        """Test adapter passes session_id and user_id to executor."""
        mock_executor = MockExecutor()
        mock_agent = MockAgent()

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
            session_id="session-123",
            user_id="user-456",
        )

        await adapter.execute(message="Test task")

        assert len(mock_executor.run_calls) == 1
        call = mock_executor.run_calls[0]
        assert call["session_id"] == "session-123"
        assert call["user_id"] == "user-456"

    @pytest.mark.asyncio
    async def test_adapter_handles_executor_error(self) -> None:
        """Test adapter handles executor errors gracefully."""

        class ErrorExecutor:
            async def run(self, agent, message: str, **kwargs):
                return Err(RuntimeError("Executor failed"))

        mock_executor = ErrorExecutor()
        mock_agent = MockAgent()

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
        )

        result = await adapter.execute(message="Test task")
        assert "failed" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_adapter_result_is_ok(self) -> None:
        """Test adapter properly handles Ok result from executor."""
        mock_executor = MockExecutor(response="Success!")
        mock_agent = MockAgent()

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
        )

        result = await adapter.execute(message="Task")
        assert "Success!" in result

    def test_adapter_preserves_agent_metadata(self) -> None:
        """Test adapter preserves original agent metadata."""
        mock_executor = MockExecutor()
        mock_agent = MockAgent(
            name="specialist",
            system_prompt="Specialized in domain knowledge",
        )

        adapter = AgentAsToolAdapter(
            agent=mock_agent,
            executor=mock_executor,
        )

        assert adapter.name == "delegate_to_specialist"
        assert "domain knowledge" in adapter.description
