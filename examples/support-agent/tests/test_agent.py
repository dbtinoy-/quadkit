"""Unit-level tests for the agent service (no boot here)."""

from __future__ import annotations

import asyncio

import pytest
from support_agent.repository.scenarios import SCENARIOS
from support_agent.services.support_service import SupportAgent, build_support_agent

from quadkit.contracts.ai.agents import AgentResponse
from quadkit.result import Ok


def _response() -> AgentResponse:
    return AgentResponse(
        message="done",
        steps=[],
        tool_calls=[],
        total_tokens=36,
        prompt_tokens=12,
        completion_tokens=24,
        total_cost=0.0,
        duration_ms=1.0,
        session_id=None,
        metadata={"strategy": "react"},
    )


class _RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    async def run(self, *, agent: object, message: str, **kw: object):
        self.calls.append((agent, message))
        return Ok(_response())


class TestBuildSupportAgent:
    def test_builds_named_agent_with_tools_and_strategy(self) -> None:
        agent = build_support_agent()

        assert agent.name == "support-agent"
        assert len(agent.tools) == 3
        assert getattr(agent, "strategy", None) is not None


class TestScenariosRegistry:
    def test_three_scenarios_registered(self) -> None:
        assert set(SCENARIOS.keys()) == {"happy", "multi_tool", "failure"}
        assert all(len(s.script) >= 2 for s in SCENARIOS.values())
        assert {v.label for v in SCENARIOS.values()} == {
            "Happy path",
            "Multi-tool",
            "Failure",
        }


class TestSupportAgentFacade:
    def test_records_last_response(self) -> None:
        executor = _RecordingExecutor()
        facade = SupportAgent(executor=executor, agent=build_support_agent())

        result = asyncio.run(facade.ask("hi"))

        assert isinstance(result, Ok)
        assert facade.last_response is not None
        assert executor.calls[0][1] == "hi"

    def test_infra_error_raises_not_wrapped(self) -> None:
        class _Broken:
            async def run(self, **kw: object):
                raise RuntimeError("not booted")

        facade = SupportAgent(executor=_Broken(), agent=build_support_agent())
        with pytest.raises(RuntimeError, match="not booted"):
            asyncio.run(facade.ask("hi"))


def test_support_strategy_has_an_explicit_five_iteration_limit() -> None:
    assert build_support_agent().strategy.max_iterations == 5


async def test_real_executor_stops_at_five_iterations_with_script_remaining() -> None:
    from support_agent.app import create_app
    from support_agent.repository.scripted_llm import ScriptedLLM

    application = create_app()
    await application.start()
    try:
        llm = await application.container.resolve(ScriptedLLM)
        llm.load(
            [
                'THOUGHT: Search again.\nACTION: search_kb\nACTION_INPUT: {"query": "order"}'
            ]
            * 6
        )
        facade = await application.container.resolve(SupportAgent)
        outcome = await facade.ask("Keep searching")
        assert outcome.is_ok(), outcome.unwrap_err()
        result = outcome.unwrap()
        assert result.metadata["max_iterations_reached"] is True
        assert result.metadata["iterations"] == 5
        assert result.tool_call_count == 5
        assert llm.remaining == 1
    finally:
        await application.stop()
