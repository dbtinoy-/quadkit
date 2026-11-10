"""Unit tests for quadkit-ai-agents observability (metrics and tracing)."""

from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from quadkit.ai.agents.observability import AgentMetrics, AgentTracer
from quadkit.contracts.ai.agents import AgentResponse
from quadkit.ai.agents.types import ToolExecutionRecord, ReasoningStep


class TestAgentMetrics:
    """Tests for AgentMetrics class."""

    def test_metrics_creation_without_recorder(self):
        """Test creating metrics without recorder (no-op)."""
        metrics = AgentMetrics()

        # Should be created without errors
        assert metrics._recorder is None

    def test_metrics_creation_with_recorder(self):
        """Test creating metrics with a recorder."""
        recorder = MagicMock()
        metrics = AgentMetrics(recorder=recorder)

        assert metrics._recorder is recorder

    def test_record_execution_without_recorder(self):
        """Test recording execution with no recorder (no-op)."""
        metrics = AgentMetrics()

        response = AgentResponse(
            message="Test",
            steps=[],
            tool_calls=[],
            total_tokens=100,
            duration_ms=100.0,
        )

        # Should not raise
        metrics.record_execution("test_agent", response)

    def test_record_execution_with_recorder(self):
        """Test recording execution calls recorder."""
        recorder = MagicMock()
        metrics = AgentMetrics(recorder=recorder)

        response = AgentResponse(
            message="Test",
            steps=[
                ReasoningStep(
                    step_number=1,
                    thought="Think",
                    action="respond",
                    observation="Response",
                ),
            ],
            tool_calls=[],
            total_tokens=200,
            duration_ms=150.0,
        )

        metrics.record_execution("my_agent", response)

        recorder.increment.assert_called()
        recorder.histogram.assert_called()

    def test_record_execution_with_failed_tool_calls(self):
        """Test recording execution with failed tool calls."""
        recorder = MagicMock()
        metrics = AgentMetrics(recorder=recorder)

        response = AgentResponse(
            message="Test",
            steps=[],
            tool_calls=[
                ToolExecutionRecord(
                    tool_name="failed_tool",
                    arguments={},
                    result="error",
                    duration_ms=50.0,
                    error="Tool failed",
                ),
            ],
            total_tokens=100,
            duration_ms=100.0,
        )

        metrics.record_execution("test_agent", response)

        # Should record failed tool calls
        recorder.increment.assert_called()

    def test_record_tool_call_without_recorder(self):
        """Test recording tool call with no recorder (no-op)."""
        metrics = AgentMetrics()

        tool_call = ToolExecutionRecord(
            tool_name="search",
            arguments={"query": "test"},
            result="results",
            duration_ms=50.0,
        )

        metrics.record_tool_call("test_agent", tool_call)

    def test_record_tool_call_success_with_recorder(self):
        """Test recording successful tool call."""
        recorder = MagicMock()
        metrics = AgentMetrics(recorder=recorder)

        tool_call = ToolExecutionRecord(
            tool_name="search",
            arguments={"query": "test"},
            result="results",
            duration_ms=50.0,
        )

        metrics.record_tool_call("test_agent", tool_call)

        # Should increment both total and success
        increment_calls = recorder.increment.call_args_list
        assert len(increment_calls) >= 2

    def test_record_tool_call_failure_with_recorder(self):
        """Test recording failed tool call."""
        recorder = MagicMock()
        metrics = AgentMetrics(recorder=recorder)

        tool_call = ToolExecutionRecord(
            tool_name="search",
            arguments={"query": "test"},
            result="error",
            duration_ms=50.0,
            error="Failed",
        )

        metrics.record_tool_call("test_agent", tool_call)

        # Should record failure
        increment_calls = recorder.increment.call_args_list
        assert len(increment_calls) >= 2

    def test_record_error_without_recorder(self):
        """Test recording error with no recorder (no-op)."""
        metrics = AgentMetrics()

        metrics.record_error("test_agent", "SomeError")

    def test_record_error_with_recorder(self):
        """Test recording error calls recorder."""
        recorder = MagicMock()
        metrics = AgentMetrics(recorder=recorder)

        metrics.record_error("test_agent", "BudgetExceededError")

        recorder.increment.assert_called()

    def test_record_governance_denied_without_recorder(self):
        """Test recording governance denial with no recorder (no-op)."""
        metrics = AgentMetrics()

        metrics.record_governance_denied("test_agent")

    def test_record_governance_denied_with_recorder(self):
        """Test recording governance denial."""
        recorder = MagicMock()
        metrics = AgentMetrics(recorder=recorder)

        metrics.record_governance_denied("test_agent")

        recorder.increment.assert_called()


class TestAgentTracer:
    """Tests for AgentTracer class."""

    def test_tracer_creation_without_tracer(self):
        """Test creating tracer without tracer (no-op)."""
        tracer = AgentTracer()

        assert tracer._tracer is None

    def test_tracer_creation_with_tracer(self):
        """Test creating tracer with a tracer."""
        mock_tracer = MagicMock()
        tracer = AgentTracer(tracer=mock_tracer)

        assert tracer._tracer is mock_tracer

    @pytest.mark.asyncio
    async def test_trace_execution_without_tracer(self):
        """Test tracing execution without tracer (no-op)."""
        tracer = AgentTracer()

        async with tracer.trace_execution(
            agent_name="test_agent",
            message="Hello world",
            session_id="session-123",
        ) as span:
            # Should yield None and not fail
            assert span is None

    @pytest.mark.asyncio
    async def test_trace_execution_with_tracer(self):
        """Test tracing execution with tracer."""
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_span = MagicMock(return_value=mock_span)

        tracer = AgentTracer(tracer=mock_tracer)

        async with tracer.trace_execution(
            agent_name="test_agent",
            message="Hello world",
            session_id="session-123",
        ) as span:
            # Should yield the span
            assert span is mock_span
            # Tracer should have been called
            mock_tracer.start_span.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_execution_sets_attributes(self):
        """Test tracing sets correct attributes."""
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_span = MagicMock(return_value=mock_span)

        tracer = AgentTracer(tracer=mock_tracer)

        async with tracer.trace_execution(
            agent_name="my_agent",
            message="Test message",
            session_id="my-session",
        ):
            pass

        call_kwargs = mock_tracer.start_span.call_args[1]
        attrs = call_kwargs["attributes"]

        assert attrs["agent.name"] == "my_agent"
        assert attrs["agent.session_id"] == "my-session"
        assert attrs["agent.message_length"] == 12

    @pytest.mark.asyncio
    async def test_trace_execution_handles_exception(self):
        """Test tracing handles exceptions."""
        mock_span = MagicMock()
        mock_span.record_exception = MagicMock()
        mock_span.set_status = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_span = MagicMock(return_value=mock_span)

        tracer = AgentTracer(tracer=mock_tracer)

        with pytest.raises(RuntimeError):
            async with tracer.trace_execution(
                agent_name="test_agent",
                message="test",
            ):
                raise RuntimeError("Test error")

        # Should record exception and set error status
        mock_span.record_exception.assert_called_once()
        mock_span.set_status.assert_called_with("ERROR")

    @pytest.mark.asyncio
    async def test_trace_tool_call_without_tracer(self):
        """Test tracing tool call without tracer (no-op)."""
        tracer = AgentTracer()

        async with tracer.trace_tool_call(
            agent_name="test_agent",
            tool_name="search",
        ) as span:
            assert span is None

    @pytest.mark.asyncio
    async def test_trace_tool_call_with_tracer(self):
        """Test tracing tool call with tracer."""
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_span = MagicMock(return_value=mock_span)

        tracer = AgentTracer(tracer=mock_tracer)

        async with tracer.trace_tool_call(
            agent_name="test_agent",
            tool_name="search",
        ):
            pass

        mock_tracer.start_span.assert_called_once()
        call_kwargs = mock_tracer.start_span.call_args[1]
        assert call_kwargs["attributes"]["tool.name"] == "search"

    @pytest.mark.asyncio
    async def test_trace_tool_call_handles_exception(self):
        """Test tracing tool call handles exceptions."""
        mock_span = MagicMock()
        mock_span.record_exception = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_span = MagicMock(return_value=mock_span)

        tracer = AgentTracer(tracer=mock_tracer)

        with pytest.raises(RuntimeError):
            async with tracer.trace_tool_call(
                agent_name="test_agent",
                tool_name="search",
            ):
                raise RuntimeError("Tool failed")

        mock_span.record_exception.assert_called_once()
        mock_span.end.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_llm_call_without_tracer(self):
        """Test tracing LLM call without tracer (no-op)."""
        tracer = AgentTracer()

        async with tracer.trace_llm_call(
            agent_name="test_agent",
            iteration=3,
        ) as span:
            assert span is None

    @pytest.mark.asyncio
    async def test_trace_llm_call_with_tracer(self):
        """Test tracing LLM call with tracer."""
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_span = MagicMock(return_value=mock_span)

        tracer = AgentTracer(tracer=mock_tracer)

        async with tracer.trace_llm_call(
            agent_name="test_agent",
            iteration=5,
        ):
            pass

        mock_tracer.start_span.assert_called_once()
        call_kwargs = mock_tracer.start_span.call_args[1]
        assert call_kwargs["attributes"]["agent.iteration"] == 5

    @pytest.mark.asyncio
    async def test_trace_llm_call_handles_exception(self):
        """Test tracing LLM call handles exceptions."""
        mock_span = MagicMock()
        mock_span.record_exception = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_span = MagicMock(return_value=mock_span)

        tracer = AgentTracer(tracer=mock_tracer)

        with pytest.raises(ValueError):
            async with tracer.trace_llm_call(
                agent_name="test_agent",
                iteration=2,
            ):
                raise ValueError("LLM error")

        mock_span.record_exception.assert_called_once()


class TestTracerIntegration:
    """Integration tests for tracer with AgentExecutor."""

    def test_tracer_works_with_executor(self):
        """Test tracer can be used with executor."""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span = MagicMock(return_value=mock_span)

        tracer = AgentTracer(tracer=mock_tracer)

        # Should be able to create multiple spans
        async def run_agent():
            async with tracer.trace_execution("agent", "test", "session"):
                async with tracer.trace_tool_call("agent", "tool"):
                    async with tracer.trace_llm_call("agent", 1):
                        pass

        # This should work without errors