from __future__ import annotations

from typing import Any

import pytest

from quadkit.ai.agents.strategies.plan_execute import PlanAndExecuteStrategy
from quadkit.ai.agents.strategies.supervisor import SupervisorStrategy
from quadkit.ai.agents.types import AgentResponse


class _Ok:
    def __init__(self, val: Any) -> None:
        self._val = val

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> Any:
        return self._val


class _Completion:
    def __init__(self, text: str) -> None:
        self.content = text


class SequenceLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._idx = 0
        self.call_count = 0

    async def complete(self, messages: Any, **kwargs: Any) -> _Ok:
        self.call_count += 1
        if self._idx < len(self._responses):
            text = self._responses[self._idx]
            self._idx += 1
        else:
            text = "THOUGHT: Done\nFINAL_ANSWER: Fallback answer"
        return _Ok(_Completion(text))


class MockAgent:
    def __init__(
        self,
        name: str = "test_agent",
        system_prompt: str = "You are a test agent.",
        tools: list[Any] | None = None,
        strategy: Any = None,
    ) -> None:
        self._name = name
        self._system_prompt = system_prompt
        self._tools = tools or []
        self._strategy = strategy

    @property
    def name(self) -> str:
        return self._name

    @property
    def tools(self) -> list[Any]:
        return self._tools

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @property
    def strategy(self) -> Any:
        return self._strategy


class MockExecutor:
    def __init__(self, response_text: str = "Agent response") -> None:
        self.response_text = response_text
        self.run_calls: list[dict[str, Any]] = []

    async def run(
        self,
        agent: Any,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> _Ok:
        self.run_calls.append(
            {
                "agent_name": agent.name,
                "message": message,
                "session_id": session_id,
            }
        )
        return _Ok(
            AgentResponse(
                message=self.response_text,
                steps=[],
                tool_calls=[],
            )
        )


class TestPlanAndExecuteStrategy:
    def test_instantiation_defaults(self) -> None:
        strategy = PlanAndExecuteStrategy()
        assert strategy.max_steps == 10
        assert strategy.max_replans == 2

    def test_instantiation_custom(self) -> None:
        strategy = PlanAndExecuteStrategy(max_steps=5, max_replans=1)
        assert strategy.max_steps == 5
        assert strategy.max_replans == 1

    @pytest.mark.asyncio
    async def test_direct_response_when_no_plan(self) -> None:
        llm = SequenceLLM(
            [
                "I can answer directly: Paris is the capital of France.",
            ]
        )
        strategy = PlanAndExecuteStrategy(max_steps=5)

        result = await strategy.execute(
            message="What is the capital of France?",
            tools=[],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert isinstance(response, AgentResponse)
        assert response.metadata.get("direct_response") is True

    @pytest.mark.asyncio
    async def test_creates_and_executes_plan(self) -> None:
        llm = SequenceLLM(
            [
                "PLAN:\n1. [REASON] Analyze the question\n2. [REASON] Formulate answer",
                "STEP_RESULT: The question asks about France's capital.",
                "STEP_RESULT: Paris is the capital of France.",
                "FINAL_ANSWER: Paris is the capital of France.",
            ]
        )
        strategy = PlanAndExecuteStrategy(max_steps=5)

        result = await strategy.execute(
            message="What is the capital of France?",
            tools=[],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert "Paris" in response.message
        assert response.metadata["strategy"] == "plan_and_execute"
        assert response.metadata["plan_steps"] == 2

    @pytest.mark.asyncio
    async def test_plan_with_tool_call(self) -> None:
        from quadkit.ai.agents import tool

        @tool
        async def search(query: str) -> str:
            """Search for information."""
            return f"Result for: {query}"

        llm = SequenceLLM(
            [
                "PLAN:\n1. [TOOL:search] Search for capital\n2. [REASON] Summarize",
                'ACTION: search\nACTION_INPUT: {"query": "capital of France"}',
                "STEP_RESULT: Based on search, Paris is the capital.",
                "FINAL_ANSWER: Paris is the capital of France.",
            ]
        )
        strategy = PlanAndExecuteStrategy(max_steps=5)

        result = await strategy.execute(
            message="What is the capital of France?",
            tools=[search],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "search"

    @pytest.mark.asyncio
    async def test_max_steps_respected(self) -> None:
        strategy = PlanAndExecuteStrategy(max_steps=3)
        assert strategy.max_steps == 3

    def test_parse_plan(self) -> None:
        text = (
            "PLAN:\n"
            "1. [TOOL:search] Search for data\n"
            "2. [REASON] Analyze results\n"
            "3. [TOOL:calculate] Compute final value\n"
        )
        plan = PlanAndExecuteStrategy._parse_plan(text)

        assert len(plan) == 3
        assert plan[0].tool_name == "search"
        assert plan[0].description == "Search for data"
        assert plan[1].tool_name is None
        assert plan[1].description == "Analyze results"
        assert plan[2].tool_name == "calculate"

    def test_parse_plan_empty(self) -> None:
        plan = PlanAndExecuteStrategy._parse_plan("Just a regular response.")
        assert plan == []

    def test_implements_strategy_protocol(self) -> None:
        from quadkit.contracts.ai.agents import StrategyProtocol

        strategy = PlanAndExecuteStrategy()
        assert isinstance(strategy, StrategyProtocol)


class TestSupervisorStrategy:
    def _make_strategy(
        self,
        agent_names: list[str] | None = None,
        executor: MockExecutor | None = None,
    ) -> SupervisorStrategy:
        names = agent_names or ["billing", "technical"]
        sub_agents = {
            name: MockAgent(name=name, system_prompt=f"You handle {name} tasks.")
            for name in names
        }
        return SupervisorStrategy(
            sub_agents=sub_agents,
            executor=executor or MockExecutor(),
            max_delegations=5,
        )

    def test_instantiation(self) -> None:
        strategy = self._make_strategy()
        assert strategy.max_delegations == 5

    @pytest.mark.asyncio
    async def test_direct_answer_without_delegation(self) -> None:
        llm = SequenceLLM(
            [
                "THOUGHT: I can answer this myself.\n"
                "FINAL_ANSWER: Hello! How can I help you?",
            ]
        )
        strategy = self._make_strategy()

        result = await strategy.execute(
            message="Hello",
            tools=[],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert "Hello" in response.message
        assert response.metadata["strategy"] == "supervisor"

    @pytest.mark.asyncio
    async def test_single_delegation(self) -> None:
        executor = MockExecutor(response_text="Your invoice is correct.")
        llm = SequenceLLM(
            [
                "THOUGHT: This is a billing question.\n"
                "ACTION: delegate_to_billing\n"
                'ACTION_INPUT: {"message": "Check the invoice"}',
                "THOUGHT: Got the billing response.\n"
                "FINAL_ANSWER: According to our billing team, your invoice is correct.",
            ]
        )
        strategy = self._make_strategy(executor=executor)

        result = await strategy.execute(
            message="Is my invoice correct?",
            tools=[],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert "invoice" in response.message.lower()
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "delegate_to_billing"
        assert len(executor.run_calls) == 1
        assert executor.run_calls[0]["agent_name"] == "billing"

    @pytest.mark.asyncio
    async def test_multiple_delegations(self) -> None:
        executor = MockExecutor(response_text="Sub-agent result.")
        llm = SequenceLLM(
            [
                "THOUGHT: Check billing first.\n"
                "ACTION: delegate_to_billing\n"
                'ACTION_INPUT: {"message": "Check charges"}',
                "THOUGHT: Now check technical.\n"
                "ACTION: delegate_to_technical\n"
                'ACTION_INPUT: {"message": "Check account status"}',
                "THOUGHT: I have all info.\n"
                "FINAL_ANSWER: Both billing and technical confirmed everything is OK.",
            ]
        )
        strategy = self._make_strategy(executor=executor)

        result = await strategy.execute(
            message="Full account review",
            tools=[],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert len(response.tool_calls) == 2
        assert len(executor.run_calls) == 2
        agents_called = [c["agent_name"] for c in executor.run_calls]
        assert "billing" in agents_called
        assert "technical" in agents_called

    @pytest.mark.asyncio
    async def test_max_delegations_reached(self) -> None:
        executor = MockExecutor(response_text="Sub-agent result.")
        llm = SequenceLLM(
            [
                "THOUGHT: Delegate.\n"
                "ACTION: delegate_to_billing\n"
                'ACTION_INPUT: {"message": "Check"}',
            ]
            * 10
        )

        strategy = SupervisorStrategy(
            sub_agents={
                "billing": MockAgent(name="billing"),
            },
            executor=executor,
            max_delegations=2,
        )

        result = await strategy.execute(
            message="Test",
            tools=[],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert response.metadata.get("max_delegations_reached") is True
        assert len(executor.run_calls) <= 2

    def test_implements_strategy_protocol(self) -> None:
        from quadkit.contracts.ai.agents import StrategyProtocol

        strategy = self._make_strategy()
        assert isinstance(strategy, StrategyProtocol)
