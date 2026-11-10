"""Tests for Result pattern in agent executor."""

import pytest
from quadkit.contracts.ai.agents import AgentError
from quadkit.ai.agents.services.result_pattern_service import AgentExecutorWithResultPattern

class TestAgentExecutorResultPattern:
    """Test Result pattern in agent executor."""

    @pytest.fixture
    def agent_executor(self) -> AgentExecutorWithResultPattern:
        """Create agent executor."""
        return AgentExecutorWithResultPattern()

    @pytest.mark.asyncio
    async def test_execute_returns_ok(self, agent_executor):
        """Verify execute returns Ok."""
        result = await agent_executor.execute("researcher", "Find Python docs", ["search", "summarize"])
        assert result.is_ok()
        output = result.unwrap()
        assert "agent" in output

    @pytest.mark.asyncio
    async def test_success_log_omits_agent_name_and_task(self, agent_executor, monkeypatch):
        from unittest.mock import MagicMock

        import quadkit.ai.agents.services.result_pattern_service as service_module

        private_agent = "private-agent-tenant-42"
        private_task = "customer=tenant-42 /srv/private/customer"
        logger = MagicMock()
        monkeypatch.setattr(service_module, "logger", logger)

        result = await agent_executor.execute(private_agent, private_task)

        assert result.is_ok()
        logged = repr(logger.mock_calls)
        assert "agent_executed" in logged
        assert private_agent not in logged
        assert private_task not in logged

    @pytest.mark.asyncio
    async def test_execute_returns_err_for_empty_agent(self, agent_executor):
        """Verify execute returns Err for empty agent name."""
        result = await agent_executor.execute("", "task")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), AgentError)

    @pytest.mark.asyncio
    async def test_execute_returns_err_for_empty_task(self, agent_executor):
        """Verify execute returns Err for empty task."""
        result = await agent_executor.execute("researcher", "")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), AgentError)
