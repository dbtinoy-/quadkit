"""Unit tests for SupervisorStrategy."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.ai.agents.strategies.supervisor import SupervisorStrategy
from quadkit.ai.agents.types import AgentResponse
from quadkit.result import Ok


class MockResponse:
    """Mock LLM response."""

    def __init__(self, content: str):
        self.content = content

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self):
        return self


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0

    async def complete(self, messages, **kwargs):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return MockResponse(resp)
        return MockResponse("THOUGHT: Done\nFINAL_ANSWER: Completed")


class MockAgent:
    """Mock agent for sub-agent."""

    def __init__(self, name: str, response: str):
        self.name = name
        self.system_prompt = f"Agent {name} system prompt"
        self._response = response

    async def run(self, message: str):
        return AgentResponse(message=self._response)


class MockExecutor:
    """Mock agent executor."""

    def __init__(self):
        self.run_calls = []

    async def run(self, agent, message: str, session_id: str | None = None, user_id: str | None = None):
        self.run_calls.append({"agent": agent, "message": message})
        return AgentResponse(message=f"Response from {agent.name}")


class TestSupervisorStrategy:
    """Tests for SupervisorStrategy."""

    def test_supervisor_delegates_to_sub_agent(self) -> None:
        """Test supervisor strategy initializes with sub-agents."""
        executor = MockExecutor()
        sub_agents = {"research": MagicMock(name="research")}

        strategy = SupervisorStrategy(
            sub_agents=sub_agents,
            executor=executor,
            max_delegations=3,
        )

        assert strategy.max_delegations == 3
        assert "research" in strategy._agent_tools

    @pytest.mark.asyncio
    async def test_supervisor_reaches_max_delegations(self) -> None:
        """Test supervisor stops at max_delegations."""

        class CountingExecutor:
            def __init__(self):
                self.call_count = 0

            async def run(self, agent, message: str, **kwargs):
                self.call_count += 1
                return Ok(AgentResponse(message=f"Sub-agent response {self.call_count}"))

        executor = CountingExecutor()

        sub_agent = MagicMock()
        sub_agent.name = "agent1"
        sub_agents = {"agent1": sub_agent}

        strategy = SupervisorStrategy(
            sub_agents=sub_agents,
            executor=executor,
            max_delegations=2,
        )

        mock_llm = MockLLM(responses=[
            'THOUGHT: Delegate to agent1\nACTION: delegate_to_agent1\nACTION_INPUT: {"message": "task 1"}',
            'THOUGHT: Delegate again\nACTION: delegate_to_agent1\nACTION_INPUT: {"message": "task 2"}',
            'THOUGHT: Continue\nACTION: delegate_to_agent1\nACTION_INPUT: {"message": "task 3"}',
        ])

        result = await strategy.execute(
            message="Test task",
            tools=[],
            history=[],
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert response.metadata.get("max_delegations_reached") is True

    @pytest.mark.asyncio
    async def test_supervisor_fallback_to_final_answer(self) -> None:
        """Test supervisor falls back when no more delegation needed."""

        executor = MockExecutor()
        sub_agents = {"assistant": MagicMock(name="assistant")}

        strategy = SupervisorStrategy(
            sub_agents=sub_agents,
            executor=executor,
            max_delegations=5,
        )

        mock_llm = MockLLM(responses=[
            "THOUGHT: I can answer directly\nFINAL_ANSWER: The answer is 42",
        ])

        result = await strategy.execute(
            message="What is the answer?",
            tools=[],
            history=[],
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert "42" in response.message
        assert len(response.steps) == 1

    @pytest.mark.asyncio
    async def test_supervisor_handles_delegation_result(self) -> None:
        """Test supervisor processes sub-agent result correctly."""

        class SubAgentExecutor:
            def __init__(self):
                self.last_message = None

            async def run(self, agent, message: str, **kwargs):
                self.last_message = message
                return Ok(AgentResponse(message=f"Found results for: {message}"))

        executor = SubAgentExecutor()

        sub_agent = MagicMock()
        sub_agent.name = "search"
        sub_agents = {"search": sub_agent}

        strategy = SupervisorStrategy(
            sub_agents=sub_agents,
            executor=executor,
            max_delegations=3,
        )

        mock_llm = MockLLM(responses=[
            'THOUGHT: I need to search for this\nACTION: delegate_to_search\nACTION_INPUT: {"message": "python"}',
            "THOUGHT: Got the results\nFINAL_ANSWER: Found results for: python",
        ])

        result = await strategy.execute(
            message="Find info about python",
            tools=[],
            history=[],
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert "Found results" in response.message
        assert executor.last_message == "python"
        assert len(response.tool_calls) == 1


class TestSupervisorParsing:
    """Tests for supervisor response parsing."""

    def test_extract_thought(self) -> None:
        """Test thought extraction."""
        text = "THOUGHT: I should search for this"
        thought = SupervisorStrategy._extract_thought(text)
        assert "search" in thought.lower()

    def test_extract_final_answer(self) -> None:
        """Test final answer extraction."""
        text = "THOUGHT: Done\nFINAL_ANSWER: The answer is 42"
        answer = SupervisorStrategy._extract_final_answer(text)
        assert answer is not None
        assert "42" in answer

    def test_extract_tool_call(self) -> None:
        """Test tool call extraction."""
        text = 'ACTION: delegate_to_search\nACTION_INPUT: {"message": "test query"}'
        tool_name, tool_args = SupervisorStrategy._extract_tool_call(text)
        assert tool_name == "delegate_to_search"
        assert "message" in tool_args

    def test_extract_tool_call_no_match(self) -> None:
        """Test tool call extraction with no match."""
        text = "Just some text without actions"
        tool_name, _ = SupervisorStrategy._extract_tool_call(text)
        assert tool_name is None
