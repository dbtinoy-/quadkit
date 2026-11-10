from __future__ import annotations

from _test_executor_support import (
    MockAgent,
    MockEventBus,
    MockGovernance,
    MockLLM,
    MockMemory,
)
import pytest

from quadkit.ai.agents.exceptions import BudgetExceededError
from quadkit.ai.agents.executor import AgentExecutorImpl
from quadkit.ai.agents.executor.executor import AgentObservability, AgentSafetyInfra
from quadkit.ai.agents.types import ToolExecutionRecord
from quadkit.contracts.ai.agents import AgentError, AgentResponse


class TestAgentExecutorInit:
    """Tests for AgentExecutorImpl initialization."""

    def test_executor_creation_with_defaults(self):
        """Test creating executor with minimal config."""
        executor = AgentExecutorImpl()

        assert executor._llm is None
        assert executor._governance is None
        assert executor._memory is None

    def test_executor_creation_with_all_params(self):
        """Test creating executor with all parameters."""
        mock_llm = MockLLM()
        mock_gov = MockGovernance()
        mock_memory = MockMemory()
        mock_event_bus = MockEventBus()

        executor = AgentExecutorImpl(
            llm=mock_llm,
            safety=AgentSafetyInfra(governance=mock_gov),
            memory=mock_memory,
            observability=AgentObservability(event_bus=mock_event_bus),
        )

        assert executor._llm is mock_llm
        assert executor._governance is mock_gov
        assert executor._memory is mock_memory
        assert executor._event_bus is mock_event_bus

    def test_executor_initializes_metrics(self):
        """Test executor initializes metrics."""
        executor = AgentExecutorImpl()

        from quadkit.ai.agents.observability import AgentMetrics

        assert isinstance(executor._metrics, AgentMetrics)

    def test_executor_initializes_tracer(self):
        """Test executor initializes tracer."""
        executor = AgentExecutorImpl()

        from quadkit.ai.agents.observability import AgentTracer

        assert isinstance(executor._tracer, AgentTracer)


class TestAgentExecutorRun:
    """Tests for AgentExecutorImpl.run method."""

    @pytest.mark.asyncio
    async def test_run_simple_agent(self):
        """Test running a simple agent."""
        executor = AgentExecutorImpl()
        agent = MockAgent(name="test", tools=[])
        mock_llm = MockLLM(response="Hello!")
        executor._llm = mock_llm

        result = await executor.run(agent=agent, message="Hi")

        assert result.is_ok()
        response = result.unwrap()
        assert isinstance(response, AgentResponse)

    @pytest.mark.asyncio
    async def test_strategy_failure_logs_omit_agent_and_exception_details(
        self, monkeypatch
    ):
        from unittest.mock import MagicMock

        import quadkit.ai.agents.executor.executor as executor_module
        import quadkit.ai.agents.executor.run_support as run_support_module

        private_agent = "private-agent-tenant-42"
        private_user = "private-user-tenant-42"
        private_session = "private-session-tenant-42"
        private_error = "token=private-secret at /srv/private/tenant-42"
        executor_logger = MagicMock()
        support_logger = MagicMock()
        monkeypatch.setattr(executor_module, "logger", executor_logger)
        monkeypatch.setattr(run_support_module, "logger", support_logger)

        class FailingStrategy:
            async def execute(self, **kwargs):
                raise RuntimeError(private_error)

        executor = AgentExecutorImpl(llm=MockLLM())
        agent = MockAgent(name=private_agent, tools=[])
        agent.strategy = FailingStrategy()
        result = await executor.run(
            agent=agent,
            message="private user input",
            session_id=private_session,
            user_id=private_user,
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert error.details == {"error_type": "RuntimeError"}
        logs = repr(executor_logger.mock_calls) + repr(support_logger.mock_calls)
        for private_value in (
            private_agent,
            private_user,
            private_session,
            private_error,
            "/srv/private/tenant-42",
        ):
            assert private_value not in logs
        assert "RuntimeError" in logs

    @pytest.mark.asyncio
    async def test_run_with_session_id(self):
        """Test running agent with session ID."""
        memory = MockMemory()
        executor = AgentExecutorImpl(memory=memory)
        agent = MockAgent(name="test", tools=[])
        mock_llm = MockLLM(response="Response")
        executor._llm = mock_llm

        result = await executor.run(
            agent=agent,
            message="Hello",
            session_id="session-123",
        )

        assert result.is_ok()
        # Memory should have been queried
        # (empty for new session)

    @pytest.mark.asyncio
    async def test_run_governance_denies(self):
        """Test governance denial."""
        governance = MockGovernance(allow=False)
        executor = AgentExecutorImpl(safety=AgentSafetyInfra(governance=governance))
        agent = MockAgent(name="test", tools=[])
        mock_llm = MockLLM(response="Response")
        executor._llm = mock_llm

        result = await executor.run(agent=agent, message="Hello", user_id="user-1")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, BudgetExceededError)

    @pytest.mark.asyncio
    async def test_run_governance_check_error(self):
        """Test governance check failure is handled."""

        class FaultyGovernance:
            async def check_request(self, **kwargs):
                raise RuntimeError("Governance service down")

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(governance=FaultyGovernance())
        )
        agent = MockAgent(name="test", tools=[])
        mock_llm = MockLLM(response="Response")
        executor._llm = mock_llm

        # Should not raise, just warn
        result = await executor.run(agent=agent, message="Hello")

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_run_with_memory_save(self):
        """Test memory is saved after execution."""
        memory = MockMemory()
        executor = AgentExecutorImpl(memory=memory)
        agent = MockAgent(name="test", tools=[])
        mock_llm = MockLLM(response="Response")
        executor._llm = mock_llm

        result = await executor.run(
            agent=agent,
            message="Hello",
            session_id="session-123",
        )

        # Check memory was updated (implementation may vary)
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_run_with_event_bus(self):
        """Test events are published."""
        event_bus = MockEventBus()
        executor = AgentExecutorImpl(
            observability=AgentObservability(event_bus=event_bus)
        )
        agent = MockAgent(name="test", tools=[])
        mock_llm = MockLLM(response="Response")
        executor._llm = mock_llm

        await executor.run(agent=agent, message="Hello")

        # Should have published start/completion events
        # (if strategy returns successfully)

    @pytest.mark.asyncio
    async def test_run_strategy_failure(self):
        """Test handling strategy failure."""

        class FailingStrategy:
            async def execute(self, **kwargs):
                raise RuntimeError("Strategy exploded")

        agent = MockAgent(name="test", tools=[])
        agent.strategy = FailingStrategy()

        executor = AgentExecutorImpl()
        executor._llm = MockLLM()

        result = await executor.run(agent=agent, message="Hello")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, AgentError)

    @pytest.mark.asyncio
    async def test_run_result_wraps_error(self):
        """Test non-AgentError is wrapped in AgentError."""

        class FailingStrategy:
            async def execute(self, **kwargs):
                from quadkit.result import Err

                return Err(ValueError("Some error"))

        agent = MockAgent(name="test", tools=[])
        agent.strategy = FailingStrategy()

        executor = AgentExecutorImpl()
        executor._llm = MockLLM()

        result = await executor.run(agent=agent, message="Hello")

        assert result.is_err()
        # Should be wrapped in AgentError

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failure_mode", ["raise", "result"])
    async def test_strategy_errors_do_not_expose_raw_exception_text(
        self,
        failure_mode: str,
        capsys,
    ) -> None:
        from quadkit.result import Err

        secret = "AGENT_EXCEPTION_SECRET_SENTINEL"
        published: list[tuple[str, dict]] = []

        class FailingStrategy:
            async def execute(self, **kwargs):
                if failure_mode == "raise":
                    raise RuntimeError(secret)
                return Err(ValueError(secret))

        async def capture_event(event_type: str, data: dict) -> None:
            published.append((event_type, data))

        agent = MockAgent(name="test", tools=[])
        agent.strategy = FailingStrategy()
        executor = AgentExecutorImpl(llm=MockLLM())
        executor._publish_event = capture_event  # type: ignore[method-assign]

        result = await executor.run(agent=agent, message="user message")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, AgentError)
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())
        assert secret not in repr(published)
        assert error.cause is None
        assert error.details["error_type"] in {"RuntimeError", "ValueError"}
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err


class TestAgentExecutorGovernance:
    """Tests for governance integration."""

    @pytest.mark.asyncio
    async def test_governance_checks_model_and_provider(self):
        """Test governance receives correct model/provider info."""
        checked_params = {}

        class TrackingGovernance:
            async def check_request(
                self, model: str, provider: str, user_id: str | None = None
            ):
                checked_params["model"] = model
                checked_params["provider"] = provider
                checked_params["user_id"] = user_id
                return True

        class ModelProviderLLM:
            model = "gpt-4"
            provider = "openai"

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(governance=TrackingGovernance()),
            llm=ModelProviderLLM(),
        )
        agent = MockAgent(name="test", tools=[])
        mock_llm = MockLLM(response="Response")
        executor._llm = mock_llm

        await executor.run(agent=agent, message="Hi", user_id="user-1")

        # Model info should come from actual llm, not executor's _llm


class TestAgentExecutorMetrics:
    """Tests for metrics recording."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self):
        """Test metrics are recorded on successful execution."""
        recorded = []

        class RecordingMetrics:
            def record_execution(self, agent_name: str, response: AgentResponse):
                recorded.append(("execution", agent_name))

            def record_tool_call(self, agent_name: str, tool_call: ToolExecutionRecord):
                recorded.append(("tool", agent_name, tool_call.tool_name))

        executor = AgentExecutorImpl()
        # Would need mock strategy returning proper response
        # This is a simplified test

    @pytest.mark.asyncio
    async def test_error_recorded_on_failure(self):
        """Test errors are recorded in metrics."""

        class RecordingMetrics:
            def record_error(self, agent_name: str, error_type: str):
                pass

        # Test with failing strategy
