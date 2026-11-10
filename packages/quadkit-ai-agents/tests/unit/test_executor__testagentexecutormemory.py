from __future__ import annotations

from _test_executor_support import (
    MockAgent,
    MockGuardPipeline,
    MockLLM,
    MockMemory,
)
import pytest

from quadkit.ai.agents.executor import AgentExecutorImpl
from quadkit.ai.agents.executor.executor import AgentSafetyInfra
from quadkit.contracts.ai.agents import AgentError, AgentResponse


class TestAgentExecutorMemory:
    """Tests for memory integration."""

    @pytest.mark.asyncio
    async def test_loads_history_from_memory(self):
        """Test history is loaded from memory."""
        existing_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        memory = MockMemory(messages=existing_history)

        executor = AgentExecutorImpl(memory=memory)
        agent = MockAgent(name="test", tools=[])
        mock_llm = MockLLM(response="Response")
        executor._llm = mock_llm

        # Pass session_id to trigger memory load
        result = await executor.run(
            agent=agent,
            message="How are you?",
            session_id="session-123",
        )

    @pytest.mark.asyncio
    async def test_saves_to_memory(self):
        """Test response is saved to memory."""
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

        # Memory should have user and assistant messages added
        assert result.is_ok()


class TestAgentExecutorCostTracking:
    """Tests for cost tracking."""

    @pytest.mark.asyncio
    async def test_cost_tracked_via_estimator(self):
        """Test cost is tracked via a real cost estimator."""

        tracked_costs = []

        class CostTrackingGovernance:
            async def check_request(self, **kwargs):
                return True

            async def track_cost(
                self, cost: float, model: str, user_id: str | None = None
            ):
                tracked_costs.append(cost)

        class FixedCostEstimator:
            def estimate_cost(
                self,
                model,
                total_tokens,
                provider=None,
                prompt_tokens=0,
                completion_tokens=0,
            ):
                return total_tokens * 0.000002

        class CountingStrategy:
            async def execute(self, message, **kwargs):
                from quadkit.result import Ok

                return Ok(
                    AgentResponse(message="done", total_tokens=1000, tool_calls=[])
                )

        agent = MockAgent(name="test", tools=[])
        agent.strategy = CountingStrategy()

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(governance=CostTrackingGovernance()),
            llm=MockLLM(),
            cost_estimator=FixedCostEstimator(),
        )

        result = await executor.run(agent=agent, message="Hi")

        assert result.is_ok()
        assert tracked_costs == [0.002]
        assert result.unwrap().total_cost == 0.002

    @pytest.mark.asyncio
    async def test_no_cost_fabrication_without_estimator(self):
        """Test cost is NOT tracked when no estimator is configured."""

        tracked_costs = []

        class CostTrackingGovernance:
            async def check_request(self, **kwargs):
                return True

            async def track_cost(
                self, cost: float, model: str, user_id: str | None = None
            ):
                tracked_costs.append(cost)

        class CountingStrategy:
            async def execute(self, message, **kwargs):
                from quadkit.result import Ok

                return Ok(
                    AgentResponse(message="done", total_tokens=1000, tool_calls=[])
                )

        agent = MockAgent(name="test", tools=[])
        agent.strategy = CountingStrategy()

        executor = AgentExecutorImpl(
            llm=MockLLM(),
            safety=None,
        )
        executor._governance = CostTrackingGovernance()

        result = await executor.run(agent=agent, message="Hi")

        assert result.is_ok()
        assert tracked_costs == []
        assert result.unwrap().total_cost == 0.0


class TestAgentExecutorGuardPipeline:
    """Tests for guard pipeline integration."""

    @pytest.mark.asyncio
    async def test_input_guard_passes(self):
        pipeline = MockGuardPipeline(input_action="allow")
        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(guard_pipeline=pipeline),
            llm=MockLLM(),
        )
        agent = MockAgent(name="test")

        result = await executor.run(agent=agent, message="Hello")

        assert result.is_ok()
        assert pipeline.input_called is True

    @pytest.mark.asyncio
    async def test_input_guard_blocks(self):
        pipeline = MockGuardPipeline(input_action="block")
        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(guard_pipeline=pipeline),
            llm=MockLLM(),
        )
        agent = MockAgent(name="test")

        result = await executor.run(agent=agent, message="Hello")

        assert result.is_err()
        assert "blocked by security guards" in str(result.unwrap_err())
        assert pipeline.input_called is True
        assert pipeline.output_called is False

    @pytest.mark.asyncio
    async def test_input_guard_redacts(self):
        pipeline = MockGuardPipeline(input_action="allow", final_content="Redacted")
        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(guard_pipeline=pipeline),
            llm=MockLLM(),
        )

        class EchoStrategy:
            async def execute(self, message, **kwargs):
                from quadkit.contracts.ai.agents import AgentResponse
                from quadkit.result import Ok

                return Ok(AgentResponse(message=message, total_tokens=0, tool_calls=[]))

        agent = MockAgent(name="test")
        agent.strategy = EchoStrategy()

        result = await executor.run(agent=agent, message="Hello")

        assert result.is_ok()
        assert result.unwrap().message == "Redacted"

    @pytest.mark.asyncio
    async def test_output_guard_blocks(self):
        pipeline = MockGuardPipeline(output_action="block")
        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(guard_pipeline=pipeline),
            llm=MockLLM(),
        )
        agent = MockAgent(name="test")

        result = await executor.run(agent=agent, message="Hello")

        assert result.is_err()
        assert "Output blocked" in str(result.unwrap_err())
        assert pipeline.input_called is True
        assert pipeline.output_called is True

    @pytest.mark.asyncio
    async def test_output_guard_redacts(self):
        pipeline = MockGuardPipeline(
            output_action="allow", final_content="Output Redacted"
        )
        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(guard_pipeline=pipeline),
            llm=MockLLM(),
        )
        agent = MockAgent(name="test")

        result = await executor.run(agent=agent, message="Hello")

        assert result.is_ok()
        assert result.unwrap().message == "Output Redacted"

    @pytest.mark.asyncio
    async def test_run_passes_pipeline_into_strategy_kwargs(self) -> None:
        pipeline = MockGuardPipeline(input_action="allow")

        class CaptureStrategy:
            seen = None

            async def execute(self, message, **kwargs):
                type(self).seen = kwargs.get("guard_pipeline")
                from quadkit.contracts.ai.agents import AgentResponse
                from quadkit.result import Ok

                return Ok(AgentResponse(message="done", total_tokens=0, tool_calls=[]))

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(guard_pipeline=pipeline),
            llm=MockLLM(),
        )
        agent = MockAgent(name="test")
        agent.strategy = CaptureStrategy()

        result = await executor.run(agent=agent, message="Hello")
        assert result.is_ok()
        assert CaptureStrategy.seen is pipeline

    @pytest.mark.asyncio
    async def test_strategy_guard_exception_maps_to_err(self):
        """A raised guard-observation exception must surface as Err(AgentError)."""

        from quadkit.ai.agents.strategies.guard_hook import (
            ToolObservationBlockedError,
        )

        class RaisingStrategy:
            async def execute(self, message, **kwargs):
                raise ToolObservationBlockedError("guard blocked tool output")

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(
                guard_pipeline=MockGuardPipeline(input_action="allow")
            ),
            llm=MockLLM(),
        )
        agent = MockAgent(name="test")
        agent.strategy = RaisingStrategy()

        result = await executor.run(agent=agent, message="Hello")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), AgentError)
        assert "blocked by guards" in str(result.unwrap_err())

    @pytest.mark.asyncio
    async def test_agent_level_pipeline_wins_over_executor_pipeline(self):
        """The agent-level override must take precedence over the DI pipeline."""

        executor_pipeline = MockGuardPipeline(input_action="block")
        agent_pipeline = MockGuardPipeline(input_action="allow")

        class CaptureStrategy:
            seen = None

            async def execute(self, message, **kwargs):
                type(self).seen = kwargs.get("guard_pipeline")
                from quadkit.contracts.ai.agents import AgentResponse
                from quadkit.result import Ok

                return Ok(AgentResponse(message="done", total_tokens=0, tool_calls=[]))

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(guard_pipeline=executor_pipeline),
            llm=MockLLM(),
        )
        agent = MockAgent(name="test")
        agent.strategy = CaptureStrategy()
        agent.guard_pipeline = agent_pipeline

        result = await executor.run(agent=agent, message="Hello")

        assert result.is_ok()
        assert CaptureStrategy.seen is agent_pipeline
        assert agent_pipeline.input_called is True
        assert executor_pipeline.input_called is False


class TestAgentExecutorGuardSanitization:
    """Guard redactions and errors must not leak unsafe content."""

    @pytest.mark.asyncio
    async def test_run_propagates_explicit_input_and_output_redactions(self) -> None:
        from types import SimpleNamespace

        from quadkit.result import Ok

        class RedactingPipeline:
            async def check_input(self, content, **kwargs):
                return Ok(
                    SimpleNamespace(
                        action="redact",
                        blocked=False,
                        final_content="safe input",
                    )
                )

            async def check_output(self, content, **kwargs):
                assert content == "raw output"
                return Ok(
                    SimpleNamespace(
                        action="redact",
                        blocked=False,
                        final_content="safe output",
                    )
                )

        class EchoStrategy:
            message: str | None = None

            async def execute(self, message, **kwargs):
                type(self).message = message
                from quadkit.result import Ok

                return Ok(
                    AgentResponse(message="raw output", total_tokens=0, tool_calls=[])
                )

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(guard_pipeline=RedactingPipeline()),
            llm=MockLLM(),
        )
        agent = MockAgent(name="test")
        agent.strategy = EchoStrategy()

        result = await executor.run(agent=agent, message="raw input")

        assert result.is_ok()
        assert EchoStrategy.message == "safe input"
        assert result.unwrap().message == "safe output"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failed_leg", ["input", "output"])
    async def test_guard_exception_text_is_not_logged_or_returned(
        self,
        failed_leg: str,
        capsys,
    ) -> None:
        from types import SimpleNamespace

        from quadkit.result import Ok

        secret = "GUARD_EXCEPTION_SECRET_SENTINEL"

        class FailingPipeline:
            async def check_input(self, content, **kwargs):
                if failed_leg == "input":
                    raise RuntimeError(secret)
                return Ok(
                    SimpleNamespace(
                        action="pass",
                        blocked=False,
                        final_content=content,
                    )
                )

            async def check_output(self, content, **kwargs):
                if failed_leg == "output":
                    raise RuntimeError(secret)
                return Ok(
                    SimpleNamespace(
                        action="pass",
                        blocked=False,
                        final_content=content,
                    )
                )

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(guard_pipeline=FailingPipeline()),
            llm=MockLLM(),
        )
        agent = MockAgent(name="test")

        result = await executor.run(agent=agent, message="user message")

        assert result.is_err()
        error = result.unwrap_err()
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err
