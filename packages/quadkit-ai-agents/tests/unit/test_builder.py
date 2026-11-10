"""Unit tests for AgentBuilder fluent API."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.ai.agents.agent.builder import AgentBuilder
from quadkit.ai.agents.agent.base import AgentBase


class TestAgentBuilder:
    """Tests for the AgentBuilder fluent API."""

    def test_basic_build(self) -> None:
        """Test building an agent with just a name."""
        agent = AgentBuilder("test_agent").build()

        assert agent.name == "test_agent"
        assert agent.system_prompt == ""
        assert agent.tools == []

    def test_with_system_prompt(self) -> None:
        """Test setting system prompt."""
        agent = (
            AgentBuilder("helper")
            .with_system_prompt("You are a helpful assistant.")
            .build()
        )

        assert agent.system_prompt == "You are a helpful assistant."

    def test_with_tools(self) -> None:
        """Test adding tools."""
        tool_a = MagicMock()
        tool_b = MagicMock()

        agent = (
            AgentBuilder("tool_agent")
            .with_tools(tool_a, tool_b)
            .build()
        )

        assert len(agent.tools) == 2

    def test_with_strategy(self) -> None:
        """Test setting strategy by name."""
        agent = (
            AgentBuilder("react_agent")
            .with_strategy("react", max_iterations=5)
            .build()
        )

        assert agent.strategy is not None

    def test_with_memory(self) -> None:
        """Test attaching memory."""
        mock_memory = MagicMock()

        agent = (
            AgentBuilder("memory_agent")
            .with_memory(mock_memory)
            .build()
        )

        assert agent.memory is mock_memory

    def test_with_guards(self) -> None:
        """Test adding guards."""
        guard_a = MagicMock()
        guard_b = MagicMock()

        agent = (
            AgentBuilder("guarded_agent")
            .with_guards(guard_a, guard_b)
            .build()
        )

        assert len(agent.guards) == 2

    def test_with_guard_pipeline(self) -> None:
        """Test setting guard pipeline."""
        mock_pipeline = MagicMock()

        agent = (
            AgentBuilder("pipeline_agent")
            .with_guard_pipeline(mock_pipeline)
            .build()
        )

        assert agent.guard_pipeline is mock_pipeline

    @pytest.mark.asyncio
    async def test_builder_pipeline_reaches_executor_run(self) -> None:
        """A with_guard_pipeline agent must have its pipeline consulted by run()."""
        from types import SimpleNamespace

        from quadkit.ai.agents.executor.executor import AgentExecutorImpl

        class RecordingStrategy:
            seen_kwarg = None

            async def execute(self, message, **kwargs):
                RecordingStrategy.seen_kwarg = kwargs.get("guard_pipeline")
                from quadkit.contracts.ai.agents import AgentResponse
                from quadkit.result import Ok

                return Ok(AgentResponse(message=message, total_tokens=0, tool_calls=[]))

        class SpyPipeline:
            input_called = False

            async def check_input(self, content, **kwargs):
                SpyPipeline.input_called = True
                from quadkit.result import Ok

                return Ok(SimpleNamespace(blocked=False, final_content=content))

            async def check_output(self, content, **kwargs):
                from quadkit.result import Ok

                return Ok(SimpleNamespace(blocked=False, final_content=content))

        from quadkit.ai.agents.agent.builder import AgentBuilder

        pipeline = SpyPipeline()
        agent = AgentBuilder("guarded_agent").with_guard_pipeline(pipeline).build()  # type: ignore[arg-type]
        agent._strategy = RecordingStrategy()  # _BuiltAgent.strategy is read-only
        executor = AgentExecutorImpl(llm=SimpleNamespace())  # pipeline absent on executor
        result = await executor.run(agent=agent, message="hello")

        assert result.is_ok()
        assert SpyPipeline.input_called is True
        assert RecordingStrategy.seen_kwarg is pipeline

    def test_with_governance(self) -> None:
        """Test governance configuration."""
        agent = (
            AgentBuilder("governed_agent")
            .with_governance(budget_limit=10.0, rate_limit=100)
            .build()
        )

        assert agent.governance_kwargs["budget_limit"] == 10.0
        assert agent.governance_kwargs["rate_limit"] == 100

    def test_with_temperature(self) -> None:
        """Test temperature setting."""
        agent = (
            AgentBuilder("temp_agent")
            .with_temperature(0.3)
            .build()
        )

        assert agent.temperature == 0.3

    def test_fluent_chaining(self) -> None:
        """Test that all methods return the builder for chaining."""
        mock_tool = MagicMock()
        mock_memory = MagicMock()

        agent = (
            AgentBuilder("chained_agent")
            .with_system_prompt("Test prompt")
            .with_tools(mock_tool)
            .with_strategy("react", max_iterations=3)
            .with_memory(mock_memory)
            .with_guards(MagicMock())
            .with_governance(budget_limit=5.0)
            .with_temperature(0.5)
            .build()
        )

        assert agent.name == "chained_agent"
        assert agent.system_prompt == "Test prompt"
        assert len(agent.tools) == 1
        assert agent.strategy is not None
        assert agent.memory is mock_memory
        assert len(agent.guards) == 1
        assert agent.temperature == 0.5

    def test_empty_name_raises(self) -> None:
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Agent name is required"):
            AgentBuilder("").build()

    def test_unknown_strategy_raises(self) -> None:
        """Test that unknown strategy name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            AgentBuilder("bad_strategy").with_strategy("nonexistent").build()

    def test_agent_base_builder_classmethod(self) -> None:
        """Test AgentBase.builder() returns an AgentBuilder."""
        builder = AgentBase.builder("my_agent")

        assert isinstance(builder, AgentBuilder)
        agent = builder.with_system_prompt("Hello").build()
        assert agent.name == "my_agent"

    def test_repr(self) -> None:
        """Test agent repr."""
        agent = AgentBuilder("repr_agent").build()
        assert "repr_agent" in repr(agent)
