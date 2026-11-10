"""Unit tests for AgentExecutorImpl.astream() streaming."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.ai.agents.executor import AgentExecutorImpl
from quadkit.ai.agents.executor.executor import AgentSafetyInfra


class MockAgent:
    """Mock agent for testing."""

    def __init__(
        self,
        name: str = "test_agent",
        tools: list | None = None,
        system_prompt: str = "",
    ):
        self.name = name
        self._tools = tools or []
        self.system_prompt = system_prompt
        self.strategy: Any = None
        self.guard_pipeline: Any = None

    @property
    def tools(self):
        return self._tools


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response: str = "test response"):
        self.response = response
        self.call_count = 0

    async def generate(self, prompt: str, **kwargs):
        self.call_count += 1
        return {"content": self.response, "usage": {"tokens": 10}}

    async def complete(self, messages, **kwargs):
        """Return a Result-like object wrapping a Completion-like object."""
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


class TestAgentStreamingHappyPath:
    """Tests for streaming under happy path."""

    @pytest.mark.asyncio
    async def test_astream_yields_started_event(self):
        """astream should yield a started event first."""
        executor = AgentExecutorImpl()
        agent = MockAgent(name="test")
        executor._llm = MockLLM(response="Hello")

        events = [e async for e in executor.astream(agent=agent, message="Hi")]
        event_types = [e.type for e in events]

        assert "started" in event_types
        assert events[0].run_id is not None

    @pytest.mark.asyncio
    async def test_astream_yields_finished_event(self):
        """astream should yield a finished event last."""
        executor = AgentExecutorImpl()
        agent = MockAgent(name="test")
        executor._llm = MockLLM(response="Hello")

        events = [e async for e in executor.astream(agent=agent, message="Hi")]
        event_types = [e.type for e in events]

        assert "finished" in event_types
        assert event_types[-1] == "finished"

    @pytest.mark.asyncio
    async def test_astream_yields_message_event(self):
        """astream should yield message events."""
        executor = AgentExecutorImpl()
        agent = MockAgent(name="test")
        executor._llm = MockLLM(response="Hello")

        events = [e async for e in executor.astream(agent=agent, message="Hi")]
        message_events = [e for e in events if e.type == "message"]

        assert len(message_events) > 0

    @pytest.mark.asyncio
    async def test_astream_event_sequence(self):
        """astream should emit events in correct sequence: started, ..., finished."""
        executor = AgentExecutorImpl()
        agent = MockAgent(name="test")
        executor._llm = MockLLM(response="Hello")

        events = [e async for e in executor.astream(agent=agent, message="Hi")]
        event_types = [e.type for e in events]

        assert "started" in event_types
        assert "finished" in event_types
        assert event_types[-1] == "finished"
        assert event_types.index("started") < event_types.index("finished")


class TestAgentStreamingToolCalls:
    """Tests for streaming tool call events."""

    @pytest.mark.asyncio
    async def test_astream_with_tools_available(self):
        """astream works when agent has tools available."""
        from dataclasses import dataclass

        @dataclass
        class MockTool:
            name: str = "search"
            description: str = "A search tool"

            @property
            def parameters_schema(self):
                return {"type": "object", "properties": {}}

            async def execute(self, **kwargs):
                return "search results"

        executor = AgentExecutorImpl()
        agent = MockAgent(name="test", tools=[MockTool()])
        executor._llm = MockLLM(response="Hello")

        events = [e async for e in executor.astream(agent=agent, message="Find info")]

        assert len(events) > 0
        assert events[0].type == "started"


class TestAgentStreamingErrors:
    """Tests for streaming error events."""

    @pytest.mark.asyncio
    async def test_astream_yields_error_on_governance_denial(self):
        """astream should yield error events when governance denies."""

        class DenyingGovernance:
            async def check_request(
                self, model: str, provider: str, user_id: str | None = None
            ):
                return False

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(governance=DenyingGovernance())
        )
        agent = MockAgent(name="test")

        events = [e async for e in executor.astream(agent=agent, message="Hi")]
        error_events = [e for e in events if e.type == "error"]

        assert len(error_events) > 0
        assert "denied" in str(error_events[0].data.get("error", "")).lower()

    @pytest.mark.asyncio
    async def test_astream_yields_finished_after_error(self):
        """astream should still yield finished after error."""

        class DenyingGovernance:
            async def check_request(
                self, model: str, provider: str, user_id: str | None = None
            ):
                return False

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(governance=DenyingGovernance())
        )
        agent = MockAgent(name="test")

        events = [e async for e in executor.astream(agent=agent, message="Hi")]
        event_types = [e.type for e in events]

        assert "error" in event_types
        assert "finished" in event_types
        error_idx = event_types.index("error")
        finished_idx = event_types.index("finished")
        assert error_idx < finished_idx


class TestAgentStreamingGovernance:
    """Tests for governance during streaming."""

    @pytest.mark.asyncio
    async def test_astream_governance_checked(self):
        """astream should still perform governance checks."""
        checked = []

        class CheckingGovernance:
            async def check_request(
                self, model: str, provider: str, user_id: str | None = None
            ):
                checked.append(
                    {"model": model, "provider": provider, "user_id": user_id}
                )
                return True

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(governance=CheckingGovernance())
        )
        agent = MockAgent(name="test")
        executor._llm = MockLLM(response="Response")

        events = [
            e
            async for e in executor.astream(agent=agent, message="Hi", user_id="user-1")
        ]

        assert len(checked) > 0
        assert checked[0]["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_astream_governance_denies_returns_error_event(self):
        """astream should yield error event when governance denies."""

        class DenyingGovernance:
            async def check_request(
                self, model: str, provider: str, user_id: str | None = None
            ):
                return False

        executor = AgentExecutorImpl(
            safety=AgentSafetyInfra(governance=DenyingGovernance())
        )
        agent = MockAgent(name="test")
        executor._llm = MockLLM(response="Response")

        events = [
            e
            async for e in executor.astream(agent=agent, message="Hi", user_id="user-1")
        ]
        error_events = [e for e in events if e.type == "error"]

        assert len(error_events) > 0


class TestAgentStreamingGuardFailClosed:
    """astream() must fail closed on guard infrastructure errors (both legs)."""

    @pytest.mark.asyncio
    async def test_streaming_fails_closed_on_guard_infrastructure_error(self) -> None:
        """A guard-pipeline crash must abort the stream (mirrors run())."""
        from quadkit.ai.agents.executor.streaming import AgentEventType

        class _CrashingPipeline:
            async def check_input(self, content, **kwargs):
                raise RuntimeError("guard service down")

            async def check_output(self, content, **kwargs):
                raise RuntimeError("guard service down")

        executor = AgentExecutorImpl(llm=MockLLM())  # type: ignore[arg-type]
        executor._guard_pipeline = _CrashingPipeline()
        agent = MockAgent(name="test")

        events: list[Any] = []
        async for event in executor.astream(agent=agent, message="hello", user_id=None):
            events.append(event)

        assert any(e.type == AgentEventType.ERROR for e in events)
        assert all(e.type != AgentEventType.MESSAGE for e in events)

    @pytest.mark.asyncio
    async def test_streaming_fails_closed_on_guard_output_error(self) -> None:
        """An output-leg guard crash must abort the stream (re-audit G1).

        The output check return was previously discarded at :150, so an
        output-side guard error still yielded MESSAGE + FINISHED(success=True).
        """
        from types import SimpleNamespace

        from quadkit.ai.agents.executor.streaming import AgentEventType
        from quadkit.result import Ok

        class _OutputCrashingPipeline:
            async def check_input(self, content, **kwargs):
                return Ok(SimpleNamespace(blocked=False, final_content=content))

            async def check_output(self, content, **kwargs):
                raise RuntimeError("guard service down")

        executor = AgentExecutorImpl(llm=MockLLM())  # type: ignore[arg-type]
        executor._guard_pipeline = _OutputCrashingPipeline()
        agent = MockAgent(name="test")

        events: list[Any] = []
        async for event in executor.astream(agent=agent, message="hello", user_id=None):
            events.append(event)

        assert any(e.type == AgentEventType.ERROR for e in events)
        assert all(e.type != AgentEventType.MESSAGE for e in events)
        finished = [e for e in events if e.type == AgentEventType.FINISHED]
        assert finished
        assert finished[-1].data.get("success") is False


class TestAgentStreamingGuardOverride:
    """Agent-level guard pipeline override must win over the executor default."""

    @pytest.mark.asyncio
    async def test_astream_consults_agent_guard_pipeline_override(self) -> None:
        """astream() must consult the agent's pipeline, not the executor's default."""
        from types import SimpleNamespace

        from quadkit.result import Ok

        class _RecordingPipeline:
            def __init__(self, name: str):
                self.name = name
                self.checks: list[str] = []

            async def check_input(self, content, **kwargs):
                self.checks.append("input")
                return Ok(SimpleNamespace(blocked=False, final_content=content))

            async def check_output(self, content, **kwargs):
                self.checks.append("output")
                return Ok(SimpleNamespace(blocked=False))

        class _RecordingStrategy:
            def __init__(self):
                self.guard_pipeline: Any = None

            async def execute(self, **kwargs):
                self.guard_pipeline = kwargs.get("guard_pipeline")
                response = SimpleNamespace(
                    message="hello back",
                    step_count=1,
                    tool_call_count=0,
                    total_tokens=10,
                    duration_ms=5,
                )
                return Ok(response)

        executor = AgentExecutorImpl(llm=MockLLM())  # type: ignore[arg-type]
        executor_pipeline = _RecordingPipeline("executor")
        executor._guard_pipeline = executor_pipeline
        agent_pipeline = _RecordingPipeline("agent")
        agent = MockAgent(name="test")
        agent.guard_pipeline = agent_pipeline
        agent.strategy = _RecordingStrategy()

        events = [
            e
            async for e in executor.astream(agent=agent, message="hello", user_id=None)
        ]

        assert any(e.type == "message" for e in events)
        assert agent.strategy.guard_pipeline is agent_pipeline
        assert executor_pipeline.checks == []


class TestAgentStreamingGuardRedaction:
    """Guard redactions must replace content before it reaches later stages."""

    @pytest.mark.asyncio
    async def test_astream_propagates_input_and_output_redactions(self) -> None:
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
                assert content == "raw output sentinel"
                return Ok(
                    SimpleNamespace(
                        action="redact",
                        blocked=False,
                        final_content="safe output",
                    )
                )

        class CapturingStrategy:
            message: str | None = None

            async def execute(self, message, **kwargs):
                self.message = message
                return Ok(
                    SimpleNamespace(
                        message="raw output sentinel",
                        step_count=1,
                        tool_call_count=0,
                        total_tokens=1,
                        duration_ms=1,
                    )
                )

        executor = AgentExecutorImpl(llm=MockLLM())  # type: ignore[arg-type]
        executor._guard_pipeline = RedactingPipeline()
        agent = MockAgent(name="test")
        agent.strategy = CapturingStrategy()

        events = [
            event
            async for event in executor.astream(
                agent=agent,
                message="raw input sentinel",
            )
        ]

        assert agent.strategy.message == "safe input"
        message_events = [event for event in events if event.type == "message"]
        finished_events = [event for event in events if event.type == "finished"]
        assert message_events[0].data["message"] == "safe output"
        assert finished_events[-1].data["message"] == "safe output"
        assert events[0].data["message_length"] == len("raw input sentinel")
        assert "message" not in events[0].data

    @pytest.mark.asyncio
    async def test_astream_error_events_do_not_expose_exception_text(
        self,
        capsys,
        monkeypatch,
    ) -> None:
        from unittest.mock import MagicMock

        import quadkit.ai.agents.executor.streaming as streaming_module

        secret = "STREAM_EXCEPTION_SECRET_SENTINEL"
        private_agent = "private-agent-tenant-42"
        logger = MagicMock()
        monkeypatch.setattr(streaming_module, "logger", logger)

        class FailingStrategy:
            async def execute(self, **kwargs):
                raise RuntimeError(secret)

        executor = AgentExecutorImpl(llm=MockLLM())  # type: ignore[arg-type]
        agent = MockAgent(name=private_agent)
        agent.strategy = FailingStrategy()

        events = [
            event
            async for event in executor.astream(
                agent=agent,
                message="user message",
            )
        ]

        assert secret not in repr(events)
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err
        logged = repr(logger.mock_calls)
        assert private_agent not in logged
        assert secret not in logged
        assert "RuntimeError" in logged
        error_events = [event for event in events if event.type == "error"]
        assert error_events
        assert error_events[-1].data["error_type"] == "RuntimeError"
