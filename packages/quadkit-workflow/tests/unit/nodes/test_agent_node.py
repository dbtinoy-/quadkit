"""Unit tests for AgentNode workflow node."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.workflow.nodes.agent_node import AgentNode
from quadkit.result import Err, Ok


class TestAgentNode:
    def test_node_initialization(self) -> None:
        agent = MagicMock()
        node = AgentNode("agent", agent=agent)
        assert node.name == "agent"
        assert node._agent is agent
        assert node._input_key == "input"
        assert node._output_key == "output"

    @pytest.mark.asyncio
    async def test_node_executes_agent(self) -> None:
        executor = MagicMock()
        executor.execute = AsyncMock(
            return_value=Ok(_MockAgentResponse("agent output"))
        )
        agent = MagicMock()
        node = AgentNode("agent", agent=agent, executor=executor)
        result = await node.execute({"input": "test input"})
        executor.execute.assert_called_once_with(agent, "test input")
        assert result == {"output": "agent output"}

    @pytest.mark.asyncio
    async def test_node_passes_context(self) -> None:
        executor = MagicMock()
        executor.execute = AsyncMock(
            return_value=Ok(_MockAgentResponse("response"))
        )
        agent = MagicMock()
        node = AgentNode(
            "agent",
            agent=agent,
            executor=executor,
            input_key="my_input",
            output_key="my_output",
        )
        result = await node.execute({"my_input": "custom input"})
        executor.execute.assert_called_once_with(agent, "custom input")
        assert result == {"my_output": "response"}

    @pytest.mark.asyncio
    async def test_node_handles_agent_error(self) -> None:
        executor = MagicMock()
        executor.execute = AsyncMock(
            return_value=Err(RuntimeError("agent failed"))
        )
        agent = MagicMock()
        node = AgentNode("agent", agent=agent, executor=executor)
        result = await node.execute({"input": "test"})
        assert "output" in result
        assert result["output"] == "Agent execution failed."
        assert "agent failed" not in result["output"]

    @pytest.mark.asyncio
    async def test_node_uses_duck_type_fallback(self) -> None:
        agent = MagicMock()
        agent.run = AsyncMock(return_value="duck type response")
        node = AgentNode("agent", agent=agent)
        result = await node.execute({"input": "test"})
        agent.run.assert_called_once_with("test")
        assert result == {"output": "duck type response"}

    @pytest.mark.asyncio
    async def test_node_handles_missing_run_method(self) -> None:
        agent = MagicMock(spec=[])
        node = AgentNode("agent", agent=agent)
        result = await node.execute({"input": "test"})
        assert "output" in result
        assert result["output"] == "Agent execution is not configured."


class _MockAgentResponse:
    def __init__(self, message: str) -> None:
        self.message = message
