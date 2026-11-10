from __future__ import annotations

from typing import Any

import pytest

from quadkit.ai.agents.delegation.agent_tool import AgentAsToolAdapter


class _Ok:
    def __init__(self, val: Any) -> None:
        self._val = val

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> Any:
        return self._val


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
        from quadkit.ai.agents.types import AgentResponse

        return _Ok(
            AgentResponse(
                message=self.response_text,
                steps=[],
                tool_calls=[],
            )
        )


class TestAgentAsToolAdapter:
    def test_name(self) -> None:
        agent = MockAgent(name="billing")
        adapter = AgentAsToolAdapter(agent=agent, executor=MockExecutor())
        assert adapter.name == "delegate_to_billing"

    def test_description(self) -> None:
        agent = MockAgent(name="billing", system_prompt="Handle billing queries.")
        adapter = AgentAsToolAdapter(agent=agent, executor=MockExecutor())
        assert "billing" in adapter.description
        assert "Handle billing" in adapter.description

    def test_parameters_schema(self) -> None:
        agent = MockAgent(name="test")
        adapter = AgentAsToolAdapter(agent=agent, executor=MockExecutor())
        schema = adapter.parameters_schema

        assert schema["type"] == "object"
        assert "message" in schema["properties"]
        assert "message" in schema["required"]

    @pytest.mark.asyncio
    async def test_execute_delegates_to_agent(self) -> None:
        executor = MockExecutor(response_text="Billing response")
        agent = MockAgent(name="billing")
        adapter = AgentAsToolAdapter(agent=agent, executor=executor)

        result = await adapter.execute(message="Check my invoice")

        assert result == "Billing response"
        assert len(executor.run_calls) == 1
        assert executor.run_calls[0]["agent_name"] == "billing"
        assert executor.run_calls[0]["message"] == "Check my invoice"

    @pytest.mark.asyncio
    async def test_execute_empty_message(self) -> None:
        executor = MockExecutor()
        agent = MockAgent(name="test")
        adapter = AgentAsToolAdapter(agent=agent, executor=executor)

        result = await adapter.execute(message="")

        assert "Error" in result
        assert len(executor.run_calls) == 0

    @pytest.mark.asyncio
    async def test_execute_passes_session_and_user(self) -> None:
        executor = MockExecutor()
        agent = MockAgent(name="test")
        adapter = AgentAsToolAdapter(
            agent=agent,
            executor=executor,
            session_id="sess-123",
            user_id="user-456",
        )

        await adapter.execute(message="Hello")

        assert executor.run_calls[0]["session_id"] == "sess-123"

    def test_satisfies_tool_protocol(self) -> None:
        from quadkit.contracts.ai.agents import ToolProtocol

        agent = MockAgent(name="test")
        adapter = AgentAsToolAdapter(agent=agent, executor=MockExecutor())
        assert isinstance(adapter, ToolProtocol)
