"""Unit tests for quadkit-ai-agents strategies."""

from __future__ import annotations

import pytest

from quadkit.ai.agents.strategies import (
    AbstractStrategy,
    PlanAndExecuteStrategy,
    ReActStrategy,
)
from quadkit.ai.agents.types import AgentResponse, ReasoningStep


class TestAbstractStrategy:
    """Tests for the AbstractStrategy class."""

    def test_base_strategy_is_abstract(self) -> None:
        """Test AbstractStrategy cannot be instantiated directly."""

        with pytest.raises(TypeError):
            AbstractStrategy()

    def test_base_strategy_subclass_must_implement_execute(self) -> None:
        """Test that subclass must implement execute method."""

        class IncompleteStrategy(AbstractStrategy):
            pass

        with pytest.raises(TypeError):
            IncompleteStrategy()


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response: str = "test response"):
        self.response = response
        self.call_count = 0

    async def generate(self, prompt: str, **kwargs):
        self.call_count += 1
        return {"content": self.response, "usage": {"tokens": 10}}

    async def complete(self, messages, **kwargs):
        """Return a Result-like object that triggers FINAL_ANSWER."""
        self.call_count += 1

        class _Completion:
            def __init__(self, text: str):
                self.content = f"THOUGHT: Responding directly\nFINAL_ANSWER: {text}"

        class _Ok:
            def __init__(self, val):
                self._val = val

            def is_ok(self):
                return True

            def is_err(self):
                return False

            def unwrap(self):
                return self._val

        return _Ok(_Completion(self.response))


class TestReActStrategy:
    """Tests for ReAct (Reasoning + Acting) strategy."""

    def test_react_strategy_exists(self) -> None:
        """Test ReActStrategy can be instantiated."""
        strategy = ReActStrategy(max_iterations=5)
        assert strategy.max_iterations == 5

    def test_react_strategy_default_iterations(self) -> None:
        """Test ReActStrategy has sensible defaults."""
        strategy = ReActStrategy()
        assert strategy.max_iterations > 0

    @pytest.mark.asyncio
    async def test_react_simple_response(self) -> None:
        """Test ReAct with a simple direct response (no tool calls)."""

        strategy = ReActStrategy(max_iterations=3)
        mock_llm = MockLLM(response="The capital of France is Paris.")

        tools = []
        history = [{"role": "user", "content": "What is the capital of France?"}]

        result = await strategy.execute(
            message="What is the capital of France?",
            tools=tools,
            history=history,
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert isinstance(response, AgentResponse)
        assert response.message is not None

    @pytest.mark.asyncio
    async def test_react_with_tool_call(self) -> None:
        """Test ReAct with a tool call in the response."""

        # Mock LLM that first returns a tool call, then a final answer.
        class ToolCallLLM:
            def __init__(self):
                self.call_count = 0

            async def complete(self, messages, **kwargs):
                self.call_count += 1

                class _Ok:
                    def __init__(self, val):
                        self._val = val

                    def is_ok(self):
                        return True

                    def is_err(self):
                        return False

                    def unwrap(self):
                        return self._val

                class _Completion:
                    def __init__(self, text: str):
                        self.content = text

                if self.call_count == 1:
                    return _Ok(
                        _Completion(
                            "THOUGHT: I need to search\n"
                            "ACTION: search\n"
                            'ACTION_INPUT: {"query": "Paris capital France"}'
                        )
                    )
                return _Ok(
                    _Completion(
                        "THOUGHT: I have the answer\n"
                        "FINAL_ANSWER: Paris is the capital of France"
                    )
                )

        strategy = ReActStrategy(max_iterations=3)
        mock_llm = ToolCallLLM()

        # Create a mock tool
        from quadkit.ai.agents import tool

        @tool
        async def search(query: str) -> list[str]:
            """Search for information."""
            return [f"Results for: {query}"]

        tools = [search]
        history = []

        result = await strategy.execute(
            message="What is Paris?",
            tools=tools,
            history=history,
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert isinstance(response, AgentResponse)
        assert len(response.tool_calls) == 1


class TestPlanAndExecuteStrategy:
    """Tests for Plan-and-Execute strategy."""

    def test_plan_execute_strategy_exists(self) -> None:
        """Test PlanAndExecuteStrategy can be instantiated."""
        strategy = PlanAndExecuteStrategy(max_steps=10)
        assert strategy.max_steps == 10

    def test_plan_execute_default_steps(self) -> None:
        """Test PlanAndExecuteStrategy has sensible defaults."""
        strategy = PlanAndExecuteStrategy()
        assert strategy.max_steps > 0

    @pytest.mark.asyncio
    async def test_plan_execute_simple_task(self) -> None:
        """Test PlanAndExecute with a simple task."""

        strategy = PlanAndExecuteStrategy(max_steps=5)
        mock_llm = MockLLM(response="I'll help you with that.")

        tools = []
        history = []

        result = await strategy.execute(
            message="Help me",
            tools=tools,
            history=history,
            llm=mock_llm,
        )

        assert result.is_ok()
        assert isinstance(result.unwrap(), AgentResponse)


class TestStrategyProtocol:
    """Tests verifying strategies implement StrategyProtocol."""

    def test_react_implements_protocol(self) -> None:
        """Test ReActStrategy can be used where StrategyProtocol is expected."""
        from quadkit.contracts.ai.agents import StrategyProtocol

        strategy = ReActStrategy()
        # Should be able to pass as StrategyProtocol
        assert isinstance(strategy, StrategyProtocol)

    def test_plan_execute_implements_protocol(self) -> None:
        """Test PlanAndExecuteStrategy can be used where StrategyProtocol is expected."""
        from quadkit.contracts.ai.agents import StrategyProtocol

        strategy = PlanAndExecuteStrategy()
        assert isinstance(strategy, StrategyProtocol)


class TestStrategyIterationLimits:
    """Tests for strategy iteration limits and termination."""

    @pytest.mark.asyncio
    async def test_react_respects_max_iterations(self) -> None:
        """Test ReAct stops after max iterations."""

        call_count = 0

        class CountingLLM:
            async def complete(self, messages, **kwargs):
                nonlocal call_count
                call_count += 1

                class _Ok:
                    def __init__(self, val):
                        self._val = val

                    def is_ok(self):
                        return True

                    def is_err(self):
                        return False

                    def unwrap(self):
                        return self._val

                class _Completion:
                    def __init__(self, text: str):
                        self.content = text

                # Always call a tool to exhaust iterations
                return _Ok(
                    _Completion(
                        "THOUGHT: I need to check\nACTION: dummy\nACTION_INPUT: {}"
                    )
                )

        from quadkit.ai.agents import tool

        @tool
        async def dummy() -> str:
            """Dummy tool."""
            return "done"

        strategy = ReActStrategy(max_iterations=2)
        mock_llm = CountingLLM()

        result = await strategy.execute(
            message="Test",
            tools=[dummy],
            history=[],
            llm=mock_llm,
        )

        # Should have stopped at max_iterations
        assert result.is_ok()
        assert call_count <= strategy.max_iterations


class TestStrategyResponseTypes:
    """Tests for strategy response structures."""

    def test_agent_response_has_required_fields(self) -> None:
        """Test AgentResponse has expected fields."""
        response = AgentResponse(
            message="Test response",
        )

        assert response.message == "Test response"
        assert isinstance(response.steps, list)
        assert isinstance(response.tool_calls, list)

    def test_reasoning_step_structure(self) -> None:
        """Test ReasoningStep has expected structure."""
        step = ReasoningStep(
            step_number=1,
            thought="I should search for this",
            action="search",
            observation="Found results",
        )

        assert step.thought == "I should search for this"
        assert step.action == "search"
        assert step.observation == "Found results"
